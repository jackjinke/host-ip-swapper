from setuptools import setup, find_packages

setup(
    name='lightsail-ip-swapper',
    version='1.0',
    packages=find_packages(),
    url='https://github.com/jackjinke/lightsail-ip-swapper',
    license='MIT',
    author='jackjinke',
    author_email='jack.kejin@gmail.com',
    description='Check the reachability of an AWS Lightsail instance, and swap the static IP if needed.',
    python_requires='>=3.6'
)
