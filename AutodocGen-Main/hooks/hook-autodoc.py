# PyInstaller hook for autodoc package
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Collect all submodules
hiddenimports = collect_submodules('autodoc')

# Collect any data files if needed
datas = collect_data_files('autodoc')
