# PhysiCell CAR-T Model Template

This directory contains only the project-specific PhysiCell template files needed
to reproduce the CAR-T model integration:

- `config/PhysiCell_settings.template.xml`
- `custom_modules/cancer_immune_3D.cpp`
- `custom_modules/cancer_immune_3D.h`

It intentionally does not include the full PhysiCell source tree, compiled
executables, object files, local run outputs, virtual environments, or sweep
artifacts.

## How to Use

1. Install or clone PhysiCell separately from its official source.
2. Create or select a PhysiCell project directory.
3. Copy `config/PhysiCell_settings.template.xml` into that project's `config/`
   directory as `PhysiCell_settings.xml`.
4. Copy the files in `custom_modules/` into the PhysiCell project's
   `custom_modules/` directory.
5. Compile the PhysiCell project with the normal PhysiCell build workflow.
6. Set `PHYSICELL_EXECUTABLE` to the compiled executable before running this
   Python workflow in external mode.

The Python package can generate additional intervention-specific XML files from
this template through the PhysiCell exporter.
