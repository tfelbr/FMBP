# FMBP

Welcome to FMBP, a Python framework for contextual reconfiguration of behavioral programs.

## Getting Started
### Setting Up the Environment
**Requirements:**
- Python >= 3.12
- poetry or pip

The project uses poetry for managing packages, but pip should work as well.

**Using poetry (recommended, mandatory for contributors):**

1. Install poetry using pip or your native package manager.
2. Clone this repository.
3. **(Optional)** You may create a custom virtual environment, like conda (tested). Useful, if your system's Python version is not sufficient. Otherwise, poetry will create a venv for you.
4. Install all dependencies: ``poetry install``

**Using pip:**

1. Clone this repository.
2. **(Recommended)** Create a virtual environment of your choice (venv, conda, ...).
3. Install all dependencies: ``pip install .``

### Running the Examples
**Requirements:**
- Rust >= 1.83.0
- (For the drone sim) OpenJDK 21
- (For UVL language support) VSCode + UVL extension

**General Setup:**
1. All examples use the UVL LSP with BP extensions. To obtain the binary, clone this repository:
    ```
    https://github.com/tfelbr/uvl-bp-lsp
    ```
   In the repository, follow the instructions to set up the VSCode IDE and to build the binary.
2. Inside the ``examples`` directory, create a file named ``config.json`` with the following content:
    ```json
    {"uvls_path": "/path/to/uvl-bp-lsp/target/release/uvls"}
    ```
   This file should contain the path to the uvls executable obtained in the previous step. All examples reference this config file.

This setup is sufficient to run the water tank and smart home examples.

**Drone Example Setup:**

The drone example is simulated in Alchemist. To set up and run the simulation environment, follow these steps:

1. Make sure OpenJDK 21 is installed and active on your PATH.
2. Clone this repository:
   ```
   https://github.com/tfelbr/fmbp-alchemist
   ```
3. Inside the repository's root, run ``./gradlew runDrones``. This command installs all dependencies, compiles the Scala code and runs the drone simulation.

**Running:**
- If you created a virtual environment, enter it. If you use poetry, you can alternatively prefix all commands with ``poetry run`` to let poetry automatically enter the environment for this command.
- Run the python file within the respective example subdirectory, either within your IDE or via command line:
    ```bash
    python examples/water_tank/water_tank.py
    python examples/smart_home/smart_home.py
    # or, if you use poetry
    poetry run python examples/water_tank/water_tank.py
    poetry run python examples/smart_home/smart_home.py
    ```
- For the drones, first run the python file and then start the simulation:
    ```bash
    python examples/drones/drones.py
    # or, if you use poetry
    poetry run python examples/drones/drones.py
    # and then
    ./gradlew runDrones # inside the root directory of the sim repo
    ```

**Altering Program Behavior:**

To get UVL language support, use VSCode to edit the supplemental UVL files to adapt the programs' behaviors at runtime.

> :warning: **Deactivate Auto Save** to prevent VSCode from saving the file too early while editing.

While you generally can edit the entire file, there are a few things to consider:
- The *ConsistencyChecker* employed in all examples ensures consistency between runtime and model in realtime.
Editing the feature model part will like cause an instant exception, as model and runtime are no longer aligned.
- The *Env* feature contains variables for context measurements. 
The actual values are acquired by the runtime and updated internally.
The water tank and smart home examples respect the initial values at start.
However, editing these values in the model while the programs are active will have no effect.
The drone scenario receives their state from Alchemist, and will not consider the initial values.
- The *Config* feature holds variables explicitly designed to be altered by the user.
- You may also adapt the list of constraints.

<p align="center">
  <img src="img/drones.gif" alt="Drone Example" />
</p>