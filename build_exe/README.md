# Compiling DET to running executable
This folder contains relevant files needed for compiling the DET into an executable file. 
The executable is generated on after every release of the DET and the resultant files are uploaded 
to the release as assets.

## Testing locally
In the event that you want to test the exe compilation locally you can follow the steps below:

Install `pyinstaller`:
> python -m pip install pyinstaller

Now create the executable (assuming you're running this on a Linux machine):
> pyinstaller --dist ./dist/linux commcare-export.spec 
 
The resultant executable file can be located under `./dist/linux/`.

The argument, `commcare-export.spec`, is a simple configuration file used by
pyinstaller which you ideally shouldn't have to ever change.