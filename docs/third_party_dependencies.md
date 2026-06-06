# Third-Party Dependencies

## PhysiCell/BioFVM

PhysiCell/BioFVM is an external simulator and is not authored by this project. This repository includes only adapter code and a small project template under `physicell_project/`.

This repository does not commit:

- the full PhysiCell source tree
- compiled PhysiCell executables
- object files
- large local simulation outputs
- fabricated time-series data

Users who want mechanistic external simulation should install and build PhysiCell separately, then provide the executable path through `PHYSICELL_EXECUTABLE`.

## Mock Outputs

Mock mode is for software testing and CI only. Mock records are fixtures, not manuscript evidence and not biological validation.
