from PyInstaller.utils.hooks import collect_data_files

# Collect data files for the phconvert package (including specs JSON files)
# so that paths like "phconvert/specs/photon-hdf5_specs.json" work in the
# frozen application.
datas = collect_data_files("phconvert")


