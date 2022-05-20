from setuptools import setup, find_packages

setup(
    name='host-ip-swapper',
    version='1.0',
    packages=find_packages(),
    url='https://github.com/jackjinke/host-ip-swapper',
    license='MIT',
    author='jackjinke',
    author_email='jack.kejin@gmail.com',
    description='Check the reachability of host, then swap the static IP and update DNS if needed.',
    python_requires='>=3.9'
)
