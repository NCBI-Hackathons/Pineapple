from setuptools import setup, find_packages

setup(
    name="LabPype",
    version="0.6.4",
    description="A Framework for Creating Pipeline Software",
    url="https://github.com/NCBI-Hackathons/LabPype",
    author="Yadi Zhou",
    author_email="yadizhou90@gmail.com",
    license="GPL-3.0",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Win32 (MS Windows)",
        "Environment :: X11 Applications :: GTK",
        "Environment :: MacOS X :: Cocoa",
        "Operating System :: Microsoft :: Windows :: Windows 10",
        "Operating System :: Microsoft :: Windows :: Windows 7",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Intended Audience :: Developers",
        "Intended Audience :: Education",
        "Intended Audience :: End Users/Desktop",
        "Intended Audience :: Science/Research",
        "Topic :: Education",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
        "Topic :: Software Development :: User Interfaces",
        "Topic :: Software Development :: Widget Sets",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
    ],
    keywords="Pipeline Workflow Widget Bioinformatics GUI",
    packages=find_packages() + ["labpype.lang", "labpype.builtin.icon"],
    package_data={
        "labpype.builtin.icon": ["*.png"],
        "labpype.lang"        : ["*.json"],
    },
    install_requires=["dynaui"],
    zip_safe=False,
)