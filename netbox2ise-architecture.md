# `netbox2ise` "Architecture" Overview 
This document provides details on how the `netbox2ise` tool is constructed and works under the hood.  The details here are most appropriate for anyone looking to develop new features or fix bugs in the tool.  Or build another tool using a similar framework.  

## The CLI Tool 
`netbox2ise` is a CLI tool written in Python.  There are 2 key libraries that are used to make the tool work. 

1. [`Click`](https://click.palletsprojects.com) 
    > Click is a Python package for creating beautiful command line interfaces in a composable way with as little code as necessary. It’s the “Command Line Interface Creation Kit”. It’s highly configurable but comes with sensible defaults out of the box.
1. [`rich`](https://rich.readthedocs.io/en/stable/introduction.html)
    > Rich is a Python library for writing rich text (with color and style) to the terminal, and for displaying advanced content such as tables, markdown, and syntax highlighted code.

The file [`netbox2ise/netbox2ise.py`](netbox2ise/netbox2ise.py) is the script that provides the CLI capabilities, and is the entrypoint to the tool.  The CLI commands are defined in this file.  As an example, here is the code that build `netbox2ise check-datafile` command. 

```python
@click.command()
@click.argument("data-file", required=True)
def check_datafile(data_file):
    """
    This command will attempt to read the data-file and verify it has all required
    data for netbox2ise
    """

    verify_datafile = test_datafile(data_file)


cli.add_command(check_datafile)
```

Note that this function doesn't have a lot of logic to itself.  Rather it calls the `test_datafile()` function to do the real work.  More on these functions and files in a bit.  

## The `utils` files 
As mentioned above, `netbox2ise.py` doesn't include much of the heavy lifting code that goes into this tool.  Rather that work is spread across a handful of "utility" scripts contained with the package.  These are: 

* [`netbox2ise/utils/netbox.py`](netbox2ise/utils/netbox.py)
    * Leverages the Public [`pynetbox`](https://pypi.org/project/pynetbox/) library
    * A set of convenience functions for pulling information from NetBox 
        * `verify_netbox` - Makes sure the NetBox server is reachable
        * `query_netbox` - Convenience function for generic queries with pynetbox 
        * `lookup_nb_devices` - Primary function used to return the list of devices and vms from NetBox
* [`netbox2ise/utils/ise.py`](netbox2ise/utils/ise.py)
    * Leverages the public library [pyise-ers](https://pypi.org/project/pyise-ers/) available at [https://github.com/falkowich/pyise-ers](https://github.com/falkowich/pyise-ers) to make ERS API calls to Cisco ISE 
    * A set of convenience functions for pulling information from ISE as well as making updates 
        * `verify_ise` - Make sure the ISE server is reachable 
        * `lookup_groups` - Return the currently configured Network Device Groups from ISE 
        * `sync_groups` - Updates the Network Device Groups in ISE given changes based on NetBox 
        * `lookup_ise_devices` - Return the currently configured Network Devices from ISE 
        * `sync_devices` - Updates the Network Devices in ISE given changes based on NetBox 
* [`netbox2ise/utils/conversion.py`](netbox2ise/utils/conversion.py)
    * A set of convenience functions for manuplating NetBox and ISE data to allow for comparison 
        * `ise_name_cleanup` - NetBox allows characters in names that aren't valid for ISE.  This function adjusts to allow them to be shared 
        * `ise_device_from_netbox` - Given a NetBox device or vm, retun an ISE network device definition 
        * `ise_groups_from_netbox` - Given a set of NetBox devices, return the set of ISE Groups that would be needed to exist. 
        * `diff_ise_groups` - Given currently configured ISE groups, and desired groups from NetBox, provide a detailed diff that can be used for updates 
        * `diff_ise_devices` - Given currently configured ISE devices, and desired devices from NetBox, provide a detailed diff that can be used for updates 
* [`netbox2ise/utils/cli_utils.py`](netbox2ise/utils/cli_utils.py)
    * Leverage the convenience functions from the other files 
    * The functions called by the CLI script to perform the individual commands.  
        * `test_datafile` - Perform verification tests on a YAML datafile to make sure it has the needed data and the servers are reachable 
        * `get_desired_devices` - Lookup the devices and vms from NetBox 
        * `lookup_current_ise_config` - Pull current ISE configuration for devices and groups 
        * `generate_desired_ise_configs` - Build the target configuration for ISE 
        * `diff_configs` - Determine the changes needed in devices and groups 
        * `print_group_diff` - Print a user readable summary of group differences determined
            * Leverages the [`rich`](https://rich.readthedocs.io/en/stable/introduction.html) Python library 
        * `print_devices_diff` - Print a user readable summary of device differences determined
            * Leverages the [`rich`](https://rich.readthedocs.io/en/stable/introduction.html) Python library 
        * `print_group_sync` - Print a user readable summary of group sync changes made
            * Leverages the [`rich`](https://rich.readthedocs.io/en/stable/introduction.html) Python library 
        * `print_devices_sync` - Print a user readable summary of device sync changes made
            * Leverages the [`rich`](https://rich.readthedocs.io/en/stable/introduction.html) Python library         

## The `files` directory 
The command `netbox2ise example-datafile` provides an example datafile format for users.  The source of this example is located in [`netbox2ise/files/datafile-example.yaml`](netbox2ise/files/datafile-example.yaml). 