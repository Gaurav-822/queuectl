from setuptools import setup, find_packages

setup(
    name="queuectl",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "queuectl=queuectl.main:main",
        ],
    },
)
