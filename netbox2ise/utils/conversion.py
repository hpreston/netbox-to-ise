"""
This is a set of functions that will take NetBox data and return data 
ready for insertion/checks with Cisco ISE.
"""

import pynetbox
from deepdiff import DeepDiff
import re


def ise_name_cleanup(name):
    """
    Remove/Replace unsupported characters from names to work with Cisco ISE.

    :param name: Input name
    :return cleaned_name
    """

    # change / -> -
    name = name.replace("/", "-")

    # remove ()
    name = name.replace("(", "").replace(")", "")

    return name


def ise_device_from_netbox(device, debug=False, tacacs_secret=None, radius_secret=None):
    """
    Create a dictionary usable with Cisco ISE as a network device from NetBox Data.

    :param device: A NetBox pynetbox.models.dcim.Devices or pynetbox.models.virtualization.VirtualMachines
    :param tacacs_secret: The TACACS Secret to configure for a device.
    :param radius_secret: The RADIUS Secret to configure for a device.
    :return a ISE compatible dictionary for device
    """

    if debug:
        print(f"device: {device}")

    ise_device = {
        "name": device.name,
        "description": f"From NetBox: {device.url}",
        "profileName": "Cisco",
        "coaPort": 1700,
        "NetworkDeviceIPList": [
            {
                "ipaddress": device.primary_ip.address.split("/")[0],
                "mask": 32,
            }
        ],
        "NetworkDeviceGroupList": ise_groups_from_netbox(device, debug=debug),
    }

    # Configure TACACS if provided
    if tacacs_secret:
        ise_device["tacacsSettings"] = {
            "sharedSecret": tacacs_secret,
            "connectModeOptions": "ON_LEGACY",
        }

    # Configure RADIUS if provided
    if radius_secret:
        ise_device["authenticationSettings"] = {
            "networkProtocol": "RADIUS",
            "radiusSharedSecret": radius_secret,
            "enableKeyWrap": False,
            "dtlsRequired": False,
            "keyEncryptionKey": "",
            "messageAuthenticatorCodeKey": "",
            "keyInputFormat": "ASCII",
            "enableMultiSecret": "false",
        }

    if debug:
        print(f"ise_device: {ise_device}")

    return ise_device


def ise_groups_from_netbox(device, debug=False):
    """
    Given a device or vm from NetBox, create the ISE Groups list for device.

    :param device: A NetBox pynetbox.models.dcim.Devices or pynetbox.models.virtualization.VirtualMachines
    :return a list of groups for ISE
    """

    groups = []

    # Location Group
    location_group = "Location#All Locations{site}{rack}"
    # Devices: Based on Rack or Site
    if isinstance(device, pynetbox.models.dcim.Devices):
        location_group = location_group.format(
            site=f"#{device.site.name}",
            rack=f"#{ise_name_cleanup(device.rack.name)}" if device.rack else "",
        )
    # VMs: Based on Cluster
    elif isinstance(device, pynetbox.models.virtualization.VirtualMachines):
        if device.cluster:
            location_group = location_group.format(
                site=f"#{device.cluster.site.name}" if device.cluster.site else "",
                rack=f"#VM Clusters#{ise_name_cleanup(device.cluster.name)}",
            )
        else:
            location_group = location_group.format(
                site=f"#{device.site.name}" if device.site else "",
                rack=f"#VM Clusters#None",
            )
    groups.append(location_group)

    # Device Type Group
    device_type_group = "Device Type#All Device Types#{manufacturer}#{device_type}"
    # Devices: Based on Device Type
    if isinstance(device, pynetbox.models.dcim.Devices):
        device_type_group = device_type_group.format(
            manufacturer=device.device_type.manufacturer.name,
            device_type=device.device_type.model,
        )
    # VMs: Based on VM Role (if no role, just VM)
    elif isinstance(device, pynetbox.models.virtualization.VirtualMachines):
        device_type_group = device_type_group.format(
            manufacturer="All VMs", device_type="General VM"
        )
    groups.append(device_type_group)

    # Custom Groups
    # Devices: Device Role
    role_group = "Device Role#Device Role{role}"
    if isinstance(device, pynetbox.models.dcim.Devices):
        role_group = role_group.format(
            role=f"#{ise_name_cleanup(device.device_role.name)}"
        )
    # VMs: VM Role
    elif (
        isinstance(device, pynetbox.models.virtualization.VirtualMachines)
        and device.role
    ):
        role_group = role_group.format(role=f"#{ise_name_cleanup(device.role.name)}")
    groups.append(role_group)

    # Tenants
    tenant_group = "Tenant#Tenant{tenant_group}{tenant}"
    tenant_group = tenant_group.format(
        tenant_group=f"#{device.tenant.group.name}"
        if device.tenant and device.tenant.group
        else "",
        tenant=f"#{device.tenant.name}" if device.tenant else "",
    )
    groups.append(tenant_group)

    # IPSEC Group
    # TODO: Method to store IPSEC status in NetBox. For now hard coded to NO
    ipsec_group = "IPSEC#Is IPSEC Device#No"
    groups.append(ipsec_group)

    return groups


def set_of_ise_groups(ise_devices):
    """
    Given a list of ise_devices, return a set of ISE Groups.

    :param ise_devices: A list of network devices with the ISE Data Model.
    :return set of ISE Network Device Groups
    """

    ise_groups = []
    for ise_device in ise_devices:
        ise_groups += ise_device["NetworkDeviceGroupList"]

    return set(ise_groups)


def diff_ise_groups(desired_groups, current_groups, desired_description=""):
    """
    Given a set of desired groups, and a dictionary for current ISE
    network device groups, determine which groups exist already,
    which are needed, and which exist in ISE but not listed as "desired".

    :param desired_groups: A set of network device group names
    :param current_groups: A dictionary of current ISE groups. {"group#name": {"id": "", "description": ""}}
    :return results dictionary:
        {
            "correct": set('group#name')},
            "incorrect": set('group#name')},
            "missing": set('group#name')},
            "extra": set('group#name')}
        }
    """

    set_current_groups = set(current_groups.keys())

    missing_groups = desired_groups.difference(set_current_groups)
    extra_groups = set_current_groups.difference(desired_groups)
    existing_groups = desired_groups.intersection(set_current_groups)

    correct_groups = set()
    incorrect_groups = set()

    for group in existing_groups:
        if current_groups[group]["description"] != desired_description:
            incorrect_groups.add(group)
        else:
            correct_groups.add(group)

    return {
        "correct": correct_groups,
        "missing": missing_groups,
        "extra": extra_groups,
        "incorrect": incorrect_groups,
    }


def diff_ise_devices(desired_devices, current_devices, debug=False):
    """
    Given a list of desired device definitions for ISE and the current ISE
    devices configured, provide a detailed diff of what changes are needed.

    :param desired_devices: A dictionary of ISE device configurations desired to be configured in ISE
    :param current_devices: A dictionary of ISE device configurations currently configured in ISE

    :return results dictionary:
        {
            "correct": ,
            "incorrect": ,
            "missing": ,
            "extra":
        }

    """

    # NOTE: Due to problems with the ISE RADIUS data for a device with RADIUS disabled having data like this
    # 'authenticationSettings': {'radiusSharedSecret': '',
    # 'enableKeyWrap': False,
    # 'dtlsRequired': False,
    # 'keyEncryptionKey': '',
    # 'messageAuthenticatorCodeKey': '',
    # 'keyInputFormat': 'ASCII',
    # 'enableMultiSecret': 'false'}
    # Rather than having NO key for 'authenticationSettings' (like an unconfigured TACACS)
    # we need to manually remove this key to provide an accurate diff check.
    for device in current_devices:
        if not "radiusSharedSecret" in current_devices[device][
            "authenticationSettings"
        ].keys() or (
            current_devices[device]["authenticationSettings"]["radiusSharedSecret"]
            == ""
            and not "networkProtocol"
            in current_devices[device]["authenticationSettings"].keys()
        ):
            if debug:
                print(
                    f'Removing "authenticationSettings" key from current {device} to reflect unconfigured RADIUS'
                )

            del current_devices[device]["authenticationSettings"]

    # Working data structure for updates
    working = {
        desired["name"]: {
            "desired": desired,
            "current": None,
            "changes": None,
            "group_changes": None,
        }
        for desired in desired_devices.values()
    }

    # Initial set check
    set_desired_device_names = set(desired_devices.keys())
    set_current_device_names = set(current_devices.keys())

    set_names_exist = set_desired_device_names.intersection(set_current_device_names)
    if debug:
        print(f"set_names_exist: {set_names_exist}")
    for device in set_names_exist:
        working[device]["current"] = current_devices[device]

    set_names_missing = set_desired_device_names.difference(set_current_device_names)
    if debug:
        print(f"set_names_missing: {set_names_missing}")

    set_names_extra = set_current_device_names.difference(set_desired_device_names)
    if debug:
        print(f"set_names_extra: {set_names_missing}")

    # IP Address Based Checks
    # Get list of currently configured IP addresses
    current_ips = {
        device["NetworkDeviceIPList"][0]["ipaddress"]: device
        for device in current_devices.values()
    }

    # For each desired_device, see if there is a current_device with the same IP address
    for desired in desired_devices.values():
        if desired["NetworkDeviceIPList"][0]["ipaddress"] in current_ips.keys():
            if debug:
                print(
                    f'desired_device {desired["name"]}s IP of {desired["NetworkDeviceIPList"][0]["ipaddress"]} is already used by current_device {current_ips[desired["NetworkDeviceIPList"][0]["ipaddress"]]["name"]}'
                )

            working[desired["name"]]["current"] = current_ips[
                desired["NetworkDeviceIPList"][0]["ipaddress"]
            ]

    # Figure out changes needed
    # NOTE: Groups are excluded from diff as group changes are handled seperately
    for device in working.values():
        if device["current"]:
            device["changes"] = DeepDiff(
                device["current"],
                device["desired"],
                exclude_paths=[
                    "root['id']",
                    "root['link']",
                    "root['NetworkDeviceGroupList']",
                    "root['tacacsSettings']['previousSharedSecret']",
                    "root['tacacsSettings']['previousSharedSecretExpiry']",
                ],
            )
            current_groups = set(device["current"]["NetworkDeviceGroupList"])
        else:
            current_groups = set()

        # Update with group updates needed
        desired_groups = set(device["desired"]["NetworkDeviceGroupList"])

        device["group_changes"] = {
            "correct": desired_groups.intersection(current_groups),
            "missing": desired_groups.difference(current_groups),
            "extra": current_groups.difference(desired_groups),
        }

    results = {"correct": {}, "incorrect": {}, "missing": {}, "extra": {}}

    for device, info in working.items():
        # Which devices need updates
        # The logic in this is likely an area for possible improvement, but it works
        if info["changes"]:
            results["incorrect"][device] = info
        else:
            if not info["current"]:
                results["missing"][device] = info
            else:
                if (
                    info["group_changes"]["missing"] != set()
                    or info["group_changes"]["extra"] != set()
                ):
                    results["incorrect"][device] = info
                else:
                    results["correct"][device] = info

    # TODO: How to find/determine "extra" devices
    #   must consider name changes...

    return results
