from setuptools import setup, find_namespace_packages

setup(
    name='host-ip-swapper',
    version='1.0',
    packages=find_namespace_packages(include=['host_ip_swapper', 'host_ip_swapper.*']),
    py_modules=['index'],
    entry_points={'console_scripts': ['host-ip-swapper=index:main']},
    install_requires=['boto3==1.34.162', 'cloudflare==2.11.1', 'dnspython==2.6.1'],
    url='https://github.com/jackjinke/host-ip-swapper',
    license='MIT',
    author='jackjinke',
    author_email='jack.kejin@gmail.com',
    description='Check host reachability, replace its public IP, and update DNS.',
    python_requires='>=3.10'
)
