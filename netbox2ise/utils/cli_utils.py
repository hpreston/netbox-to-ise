from os import getenv
import yaml
import json
import importlib

from rich.console import Console
from rich.table import Table
from rich import print as rprint

from netbox2ise.utils.netbox import verify_netbox, lookup_nb_devices

from netbox2ise.utils.conversion import (
    set_of_ise_groups,
    diff_ise_groups,
    diff_ise_devices,
)


from netbox2ise.utils.conversion import ise_device_from_netbox

# Supported ciscoise-sdk API versions
ciscoise_sdk_supported_api_versions = ["3.1.0", "3.1_Patch_1", "3.2_beta", "3.3_patch_1"]

console = Console()

def get_module_by_version(version):
    """
    Dynamically load the correct ISE library based on the version provided
    If the version is not supported, raise a ValueError.
    Choices:
        - "legacy": Use the original ISE library (pyise-ers)
        - See `ciscoise_sdk_supported_api_versions` static variable above for supported versions
          that use the new ISE library (ciscosdk-ise)
    :param version: The version of ISE to use
    :type version: str
    :return: The ISE library module
    :rtype: module
    """
    if version == "legacy":
        return importlib.import_module("netbox2ise.utils.ise")
    elif version in ciscoise_sdk_supported_api_versions:
        return importlib.import_module("netbox2ise.utils.ciscosdk_ise")
    else:
        raise ValueError(
            f"Invalid version: {version}. Supported versions are: "
            f"legacy, {', '.join(ciscoise_sdk_supported_api_versions)}"
        )

def test_datafile(data_file):
    """
    This command will attempt to read the data-file and verify it has all required
    data for netbox2ise
    """

    errors = []
    with open(data_file) as f:
        yaml_datafile = yaml.safe_load(f.read())

    # NetBox and ISE Servers
    console.rule("[bold black]Checking NetBox and ISE Servers", align="left")
    defaults = yaml_datafile["defaults"] if yaml_datafile.get("defaults") else None
    if defaults:
        netbox_server = (
            defaults["netbox_server"] if defaults.get("netbox_server") else None
        )
        if netbox_server:
            # Read token from ENV if not in data-file
            netbox_server["token"] = (
                netbox_server["token"]
                if netbox_server.get("token")
                else getenv("NETBOX_TOKEN")
            )

            # Attempt to connect to the netbox server
            netbox_test = verify_netbox(netbox_server)
            if netbox_test["status"]:
                rprint(
                    f"[blue]NetBox Server {netbox_server['url']} successfully connected to."
                )
            else:
                rprint(
                    f"[red]Problem connecting to NetBox Server {netbox_server['url']}."
                )
        else:
            errors.append("netbox_server data is missing.")

        ise_server = defaults["ise_server"] if defaults.get("ise_server") else None
        if ise_server:
            # Read user/pass from ENV if not in data-file
            ise_server["username"] = (
                ise_server["username"]
                if ise_server.get("username")
                else getenv("ISE_USER")
            )
            ise_server["password"] = (
                ise_server["password"]
                if ise_server.get("password")
                else getenv("ISE_PASS")
            )
            ise_server["version"] = (
                ise_server["version"]
                if ise_server.get("version")
                else getenv("ISE_VERSION")
            )

            if not ise_server["version"]:
                ise_server["version"] = "legacy"
                rprint(
                    "[yellow]ISE version not specified in data-file or environment. Defaulting to 'legacy'."
                )

            # Check if the version string provided in the datafile is valid
            if ise_server["version"] not in ["legacy"] + ciscoise_sdk_supported_api_versions:
                errors.append(
                    f"Invalid ISE version {ise_server['version']}. "
                    f"Must be one of: legacy, {', '.join(ciscoise_sdk_supported_api_versions)}. Exiting script"
                )
            else:
                # dynamically load the correct ise library
                ise = get_module_by_version(ise_server["version"])
                if not ise:
                    errors.append(
                        f"Unable to load ISE library for version {ise_server['version']}. "
                    )
                else:
                    # Attempt to conenct to ise server
                    ise_test = ise.verify_ise(ise_server)
                    if ise_test["status"]:
                        rprint(
                            f"[blue]ISE Server {ise_server['address']} successfully connected to."
                        )
                    else:
                        rprint(
                            f"[red]Problem connecting to ISE Server {ise_server['address']}."
                        )
        else:
            errors.append("ise_server data is missing.")
    else:
        errors.append("defaults section of data-file not found.")

    # TODO: Add more verifications for other components of the file

    if len(errors) > 0:
        rprint(f"[red]Errors:[/red]\n {errors}")
        return False

    return yaml_datafile


def get_desired_devices(netbox_server, job, debug=False):
    """
    Return a desired_devices list from a NetBox server for a 'job'
    """

    netbox_devices = lookup_nb_devices(
        netbox_server=netbox_server,
        sites=job["netbox_query"]["sites"] if job["netbox_query"].get("sites") else [],
        device_types=job["netbox_query"]["device_types"]
        if job["netbox_query"].get("device_types")
        else [],
        device_roles=job["netbox_query"]["device_roles"]
        if job["netbox_query"].get("device_roles")
        else [],
        tenants=job["netbox_query"]["tenants"]
        if job["netbox_query"].get("tenants")
        else [],
        status=job["netbox_query"]["status"]
        if job["netbox_query"].get("status")
        else [],
        debug=debug,
    )
    if debug:
        console.log(f"job: {job['name']}")
        console.log(
            f"netbox devices: {', '.join( [ device.name for device in netbox_devices['devices'] ])}"
        )
        console.log(
            f"netbox vms: {', '.join( [ vm.name for vm in netbox_devices['vms'] ])}"
        )

    # create the desired ise-device configurations for the netbox-quere
    desired_devices = {}
    for device in netbox_devices["devices"]:
        desired_devices[device["name"]] = ise_device_from_netbox(
            device,
            tacacs_secret=job["ise_config"]["tacacs"]["secret"]
            if job["ise_config"].get("tacacs")
            else None,
            radius_secret=job["ise_config"]["radius"]["secret"]
            if job["ise_config"].get("radius")
            else None,
            debug=debug,
        )
    for vm in netbox_devices["vms"]:
        desired_devices[vm["name"]] = ise_device_from_netbox(
            vm,
            tacacs_secret=job["ise_config"]["tacacs"]["secret"]
            if job["ise_config"].get("tacacs")
            else None,
            radius_secret=job["ise_config"]["radius"]["secret"]
            if job["ise_config"].get("radius")
            else None,
            debug=debug,
        )

    return desired_devices


def lookup_current_ise_config(ise_server, debug):
    """
    Lookup and return teh current ISE devices and and Groups

    :param ise_server:
    :return (current_devices, current_groups)
    """
    # Import the correct ISE module based on the version
    ise = get_module_by_version(ise_server["version"])
    
    current_devices = ise.lookup_ise_devices(ise_server, debug=debug)
    if debug:
        console.log(f"current_devices: {current_devices}")
    current_groups = ise.lookup_groups(ise_server, debug=debug)
    if debug:
        console.log(f"current_groups: {current_groups}")

    return (current_devices, current_groups)


def generate_desired_ise_config(netbox_server, job, debug):
    """
    Generate desired configuration for ISE from NetBox Job

    :param ise_server:
    :return (desired_devices, desired_groups)
    """

    desired_devices = get_desired_devices(netbox_server, job, debug=debug)
    if debug:
        console.log(f"desired_devices: {desired_devices}")
    desired_groups = set_of_ise_groups(desired_devices.values())
    if debug:
        console.log(f"desired_groups: {desired_groups}")

    return (desired_devices, desired_groups)


def diff_configs(
    current_devices=None,
    desired_devices=None,
    current_groups=None,
    desired_groups=None,
    desired_group_description="From NetBox SoT",
    debug=False,
):
    """
    Given current and desired configs for devices or groups, generate and return the differences.

    :param current_devices:
    :param desired_devices:
    :param current_groups:
    :param desired_groups:
    :return (devices_diff, groups_diff)
    """

    devices_diff = (
        diff_ise_devices(desired_devices, current_devices, debug=debug)
        if desired_devices
        else None
    )
    if debug:
        console.log(f"devices_diff: {devices_diff}")
    groups_diff = (
        diff_ise_groups(
            desired_groups,
            current_groups,
            desired_description=desired_group_description,
        )
        if current_groups and desired_groups
        else None
    )
    if debug:
        console.log(f"groups_diff: {groups_diff}")

    return (devices_diff, groups_diff)


def print_group_diff(groups_diff):
    """
    Print a nice table displaying the groups_diff

    :param groups_diff:
    """

    colors = {
        "correct": "blue",
        "incorrect": "#F39C12",
        "missing": "red",
        "extra": "purple",
    }

    # Print table of desired devices
    table = Table(
        title="Network Device Group Differences", show_lines=True, expand=True
    )
    table.add_column("Group Name", justify="left", no_wrap=True)
    table.add_column("Status", justify="left", no_wrap=True)

    for status in groups_diff:
        for group in groups_diff[status]:
            table.add_row(
                group, status, style=colors[status] if colors.get(status) else "black"
            )

    console.print(table)


def print_devices_diff(devices_diff):
    """
    Print a nice table displaying the groups_diff

    :param devices_diff:
    """

    colors = {
        "correct": "blue",
        "incorrect": "#F39C12",
        "missing": "red",
        "extra": "purple",
    }

    # Print table of desired devices
    table = Table(title="Network Device Differences", show_lines=True, expand=True)
    table.add_column("Device Name", justify="left", no_wrap=True)
    table.add_column("Status", justify="left", no_wrap=True)
    table.add_column("Field Changes", justify="left", no_wrap=False)
    table.add_column("Network Device Groups")

    total_devices = 0

    for status in devices_diff:
        total_devices += len(devices_diff[status])
        for device_name, diff_details in devices_diff[status].items():
            # Field Changes
            if status == "incorrect":
                if diff_details["changes"]:
                    changes = []

                    # Look for any added items
                    dictionary_item_added = (
                        diff_details["changes"]["dictionary_item_added"]
                        if "dictionary_item_added" in diff_details["changes"].keys()
                        else list()
                    )
                    for added_item in dictionary_item_added:
                        changes.append(
                            f"[red]New Configuration under {added_item}[/red]"
                        )

                    # Look for any changed values
                    values_changed = (
                        diff_details["changes"]["values_changed"]
                        if "values_changed" in diff_details["changes"].keys()
                        else dict()
                    )
                    for field, change in values_changed.items():
                        changes.append(
                            f'[black]{field}[/black] \n  from [red]{change["old_value"]}[/red] \n  to [blue]{change["new_value"]}[/blue]'
                        )
                    changes = "\n".join(changes)
                else:
                    changes = ""
            elif status == "missing":
                changes = []
                for field, value in diff_details["desired"].items():
                    if field != "NetworkDeviceGroupList":
                        changes.append(f"{field}: {value}")
                changes = "\n".join(changes)
            else:
                changes = ""

            # Group Changes
            group_changes = []
            if status != "correct":
                for group_status, groups in diff_details["group_changes"].items():
                    if len(groups) > 0:
                        group_changes.append(
                            f"[{colors[group_status]}]{group_status}[/{colors[group_status]}]"
                        )
                        for group in groups:
                            group_changes.append(
                                f"[{colors[group_status]}] - {group}[/{colors[group_status]}]"
                            )

            table.add_row(
                device_name,
                status,
                changes,
                "\n".join(group_changes),
                style=colors[status] if colors.get(status) else "black",
            )

    console.print(table)
    console.print(f"Total Devices: {total_devices}")


def print_group_sync(groups_sync):
    """
    Print a nice table displaying the groups_sync

    :param groups_sync:
    """

    colors = {
        "created": "blue",
        "updated": "#F39C12",
        "deleted": "red",
    }

    # Print table of desired devices
    table = Table(
        title="Network Device Group Sync Results", show_lines=True, expand=True
    )
    table.add_column("Group Name", justify="left", no_wrap=True)
    table.add_column("Status", justify="left", no_wrap=True)

    for status in groups_sync:
        for group in groups_sync[status]:
            table.add_row(
                group, status, style=colors[status] if colors.get(status) else "black"
            )

    console.print(table)


def print_devices_sync(devices_sync):
    """
    Print a nice table displaying the devices_sync

    :param devices_sync:
    """

    colors = {
        "created": "blue",
        "updated": "#F39C12",
        "deleted": "red",
    }

    # Print table of desired devices
    table = Table(title="Network Devices Sync Results", show_lines=True, expand=True)
    table.add_column("Device Name", justify="left", no_wrap=True)
    table.add_column("Status", justify="left", no_wrap=True)
    table.add_column("Results", justify="left", no_wrap=False)

    for status in devices_sync:
        for device, updates in devices_sync[status].items():
            # Build appropriate results string for table
            if status == "created":
                result = updates["response"]
            elif status == "updated":
                results_list = []
                # ciscoisesdk uses 'UpdatedFieldsList' for dictionary key for updates
                if 'UpdatedFieldsList' in updates:
                    update = updates['UpdatedFieldsList']
                # pyise-ers uses 'response' for dictionary key for updates
                else:
                    update = updates['response']

                for field in update["updatedField"]:
                    # Bug in ISE API response for updated description field.
                    #  Instead of a simple string with new description, a JSON string provided with extra details
                    #       {
                    #           "field": "Description",
                    #           "oldValue": "{\"description\":\"\",\"secondRadiusSharedSecret\":\"\",\"enableMultiSecret\":\"false\"}",
                    #           "newValue": "{\"description\":\"NEW\",\"secondRadiusSharedSecret\":\"\",\"enableMultiSecret\":\"false\"}"
                    #       },
                    # To work around this, if the field is "Description", will need to be read in as json and worked with
                    if field["field"] == "Description":
                        field["oldValue"] = json.loads(field["oldValue"])["description"]
                        field["newValue"] = json.loads(field["newValue"])["description"]

                    # Some fields (like Groups and IP addresses) are split across 2 messages
                    old_message = (
                        f' was "{field["oldValue"]}"' if field.get("oldValue") else ""
                    )
                    new_message = (
                        f' now "{field["newValue"]}"' if field.get("newValue") else ""
                    )

                    results_list.append(
                        f'Field {field["field"]}{old_message}{new_message}'
                    )
                result = "\n".join(results_list)
            else:
                result = "N/A"

            table.add_row(
                device,
                status,
                result,
                style=colors[status] if colors.get(status) else "black",
            )

    console.print(table)
