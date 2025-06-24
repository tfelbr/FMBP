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
- Run the python file within the respective example subdirectory, either within your IDE or via command line:
   ```bash
   python water_tank.py
   ```
- For the drones, first run the python file and then start the simulation:
   ```bash
   python drones.py # inside the example directory of this repo
   ./gradlew runDrones # inside the root directory of the sim repo
   ```