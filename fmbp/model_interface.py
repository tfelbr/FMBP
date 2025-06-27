import json
import logging
from abc import ABC, abstractmethod
from json import JSONDecodeError
from pathlib import Path
from subprocess import Popen, PIPE
from typing import Optional

from sansio_lsp_client import Client, JSONDict, TextDocumentItem, Event, TextDocumentIdentifier, \
    VersionedTextDocumentIdentifier, TextDocumentContentChangeEvent, ShowMessage, PublishDiagnostics, Diagnostic, \
    DiagnosticSeverity

from fmbp.const import CONTEXT_DATA, RUNTIME_CONFIG
from fmbp.fm import Feature


class ModelInterface(ABC):
    def __init__(self) -> None:
        self.model_info = self._acquire_model_info()

    @abstractmethod
    def acquire_configuration(
            self,
            context_vars: CONTEXT_DATA | None = None,
    ) -> RUNTIME_CONFIG | None:
        pass

    @abstractmethod
    def _acquire_model_info(self) -> tuple[Feature, ...]:
        pass

    @abstractmethod
    def _update(self) -> None:
        pass

    def update(self) -> None:
        self._update()
        self.model_info = self._acquire_model_info()


class FileBasedModelInterface(ModelInterface, ABC):
    def __init__(self, model: Path) -> None:
        super().__init__()
        self.model = model


class FlexibleClient(Client):
    def send_request(
        self,
        method: str,
        params: Optional[JSONDict] = None,
    ) -> None:
        self._send_request(method, params)



class LSPConnection:
    def __init__(self, path_to_server: Path) -> None:
        self.__server = Popen(
            path_to_server,
            stdin=PIPE,
            stdout=PIPE,
            stderr=PIPE,
        )
        self.total = 0

    def send(self, content: bytes) -> None:
        assert self.__server.stdin is not None
        self.__server.stdin.write(content)
        self.__server.stdin.flush()

    def recv(self) -> bytes:
        assert self.__server.stdout is not None
        headers = b""
        while not headers.endswith(b"\r\n\r\n"):
            headers += self.__server.stdout.read(1)
        size = int(headers.split(b": ")[1].split(b"\r\n\r\n")[0])
        for b in range(size):
            headers += self.__server.stdout.read(1)
        # print(headers)
        return headers


class DefectUVLModel(Exception):
    pass


def _maybe_raise_defect(diagnostics: list[Diagnostic]) -> None:
    defects = [diagnostic for diagnostic in diagnostics if diagnostic.severity == DiagnosticSeverity.ERROR]
    if len(defects) > 0:
        defects_message = "\n".join(
            f"{defect.range.start} to {defect.range.end}: {defect.message}"
            for defect in defects
        )
        raise DefectUVLModel(f"UVL model has errors\n\n{defects_message}")



class UVLLSPInterface(FileBasedModelInterface):
    def __init__(self, model: Path, lsp: Path) -> None:
        self.__model = model
        self.__server = lsp
        self.__connection = LSPConnection(lsp)
        self.__client = FlexibleClient()
        self.__initialize_connection()
        self.__file_version = 1
        self.open_uvl()
        super().__init__(model)

    def __initialize_connection(self) -> None:
        if not self.__client.is_initialized:
            self.__send_and_receive()
            assert self.__client.is_initialized
            # extra send for initialized response
            self.__send_and_receive()
            # receive for extra watchers (don't ask me why they do it...)
            self.__receive()

    def __receive(self) -> tuple[Event, ...]:
        events = []
        data = self.__connection.recv()
        try:
            for event in self.__client.recv(data):
                if isinstance(event, PublishDiagnostics):
                    _maybe_raise_defect(event.diagnostics)
                # print(event)
                events.append(event)
        except NotImplementedError:
            pass
        return tuple(events)

    def __send(self) -> None:
        to_send = self.__client.send()
        # print(to_send)
        self.__connection.send(to_send)

    def __send_and_receive(self) -> tuple[Event, ...]:
        self.__send()
        return self.__receive()

    def open_uvl(self) -> tuple[Event, ...]:
        with self.__model.open() as uvl_file:
            self.__client.did_open(
                TextDocumentItem(
                    uri=self.__model.as_uri(),
                    languageId="uvl",
                    version=self.__file_version,
                    text=uvl_file.read(),
                )
        )
        return self.__send_and_receive()

    def change_uvl(
            self,
            uvl_content: str,
    ) -> tuple[Event, ...]:
        self.__file_version += 1
        document = VersionedTextDocumentIdentifier(uri=self.__model.as_uri(), version=self.__file_version)
        changes = [TextDocumentContentChangeEvent(text=uvl_content, range=None, rangeLength=None)]
        self.__client.did_change(document, changes)
        first = self.__send_and_receive()
        second = self.__receive()
        return first + second

    def close_uvl(self) -> tuple[Event, ...]:
        self.__client.did_close(TextDocumentIdentifier(uri=self.__model.as_uri()))
        return self.__send_and_receive()

    def acquire_configuration(
            self,
            context_vars: CONTEXT_DATA | None = None,
    ) -> RUNTIME_CONFIG | None:
        config_path = Path(f"./{self.__model.name}-1.json")
        try:
            command = "uvls/generate_configurations"
            arguments = [self.__model.as_uri(), 1]
            if context_vars is not None:
                arguments.append(context_vars)
            self.__client.send_request(
                "workspace/executeCommand",
                {"command": command, "arguments": arguments},
            )
            events = self.__send_and_receive()
            if len(events) > 0:
                event = events[0]
                if isinstance(event, ShowMessage):
                    raise ValueError("No SAT solution for this file")
            # The UVL language server exports generated configurations into a json file.
            # We wait for the file to be created and read it then.
            while not config_path.exists():
                pass
            with config_path.open() as config_file:
                # It seems as if UVL first creates the file and then writes to it, which is not an atomic process.
                # This sometimes causes a race condition when we try to read the file before it is finished.
                # As a consequence, incomplete data gets parsed and json complains.
                # If this happens 10 times in a row, we log and return None.
                retries = 0
                while True:
                    try:
                        json_data = json.loads(config_file.read())
                    except JSONDecodeError as e:
                        if retries > 10:
                            logging.error(e)
                            return None
                        retries += 1
                    else:
                        break
        finally:
            if config_path.exists():
                config_path.unlink()
        return {
            key: value
            for key, value in json_data["config"].items()
            if isinstance(value, bool) and "." not in key
        }

    def _acquire_model_info(self) -> tuple[Feature, ...]:
        self.__client.send_request(
            "workspace/executeCommand",
            {"command": "uvls/export_model", "arguments": [self.__model.as_uri()]},
        )
        # For some reason, the LSP sends OK before the data sometimes
        events = self.__send_and_receive()
        if len(events) == 0:
            events = self.__receive()
        else:
            self.__receive()
        event = events[0]
        if not isinstance(event, ShowMessage):
            raise TypeError()
        return tuple(Feature.from_dict(data) for data in json.loads(event.message))

    def _update(self) -> None:
        self.change_uvl(self.__model.read_text())
