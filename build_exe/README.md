# Compiling DET to running executable
This folder contains relevant files needed (dockerfiles and scripts) for compiling the DET into an executable file. 
The file structure is segmented into the different operating systems the resultant executable will
be compatible on. 

(Currently only Linux is supported; Windows coming soon)


## How it works
In order to compile the DET script into a working executable we use [pyinstaller](https://github.com/pyinstaller/pyinstaller) in a containerized
environment. The dockerfile is an edited version from [cdrx/docker-pyinstaller](https://github.com/cdrx/docker-pyinstaller)
which is slightly modified to suit our use-case.

When a new release of the DET is published, a workflow is triggered which automatically compiles an executable from the latest
code using the custom built docker image, `dimagi/commcare-export-pyinstaller-linux`, then uploads it to the release as an asset. 

If you ever have to compile the executable yourself you can follow the section below, *Compiling executable files locally*, on how to compile an executable locally.


Compiling executable files locally
-----------------------------------
The DET executable files are compiled using a tool called [pyinstaller](https://pyinstaller.org/en/stable/).
Pyinstaller is very easy to use, but only works out-of-the-box for Linux as support for cross-compilation was
dropped in earlier releases. Another tool, [wine](https://www.winehq.org/), can be used in conjuction with
pyinstaller to compile the Windows exe files (not yet supported).

Luckily in the world we live containerization is a thing. We use a docker container, `dimagi/commcare-export-pyinstaller-linux`
(based on [docker-pyinstaller](https://github.com/cdrx/docker-pyinstaller)), which allows you to seamlessly compile the Linux binary, so we don't ever have to worry about installing any additional packages ourselves.

To compile a new linux binary, first make sure you have the docker image used to generate the executable:
> docker pull dimagi/commcare-export-pyinstaller-linux:latest

Now it's really as simple as running
> docker run -v "$(pwd):/src/" dimagi/commcare-export-pyinstaller-linux

Once you're done, the compiled file can be located at `./dist/linux/commcare-export`.

The tool needs two files to make the process work:
1. `commcare-export.spec`: this file is used by `pyinstaller` and is already defined and sits at the top of this project.
It shouldn't be necessary for you to change any parameters in the file.
2. `requirements.txt`: this file lists all the necessary packages needed for running commcare-export.


## Updating the docker image
Are you sure you need to update the image?

Just checking...


If it's needed to make any changes (for whatever reason) to the docker image you can rebuild the image as follows:
> docker build -f ./build_exe/linux/Dockerfile-py3-amd64 -t dimagi/commcare-export-pyinstaller-linux:latest .

Now upload the new image to dockerhub (remember to log in to the account first!):
> docker image push dimagi/commcare-export-pyinstaller-linux:latest
