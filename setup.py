from setuptools import setup, find_packages

setup(
    name='netbox2ise',
    version='0.3',
    packages=find_packages(),
    package_data={
        "": ["*.yaml"],
    },
    include_package_data=True,
    install_requires=[
        'Click',
        'pyise-ers==0.2.0.1',
        'pynetbox==7.5.0',
        'deepdiff==5.8.1',
        'PyYAML==6.0.2',
        'rich==12.5.1',
        'urllib3==1.26.6',
        'ciscoisesdk==2.3.1'
    ],
    entry_points='''
        [console_scripts]
        netbox2ise=netbox2ise.netbox2ise:cli
    ''',
)
