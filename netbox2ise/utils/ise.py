"""
This is a set of Cisco ISE related functions used to retrieve and update data
"""

from pyiseers import ERS
import traceback


def verify_ise(ise_server):
    """
    Verify an ISE Server is reachable

    :param ise_server: A dictionary {"address": "192.168.0.11", "username": "admin", "password": "password"}
    :return status dictionary
    """

    ise = ERS(
        ise_node=ise_server["address"],
        ers_user=ise_server["username"],
        ers_pass=ise_server["password"],
        verify=False,
        disable_warnings=True,
        timeout=10,
    )

    try:
        devices = ise.get_devices()["response"]
        if isinstance(devices, str) and devices == "Unauthorized":
            return {"status": False, "message": f"Unable to authenticate to Cisco ISE"}
        elif isinstance(devices, list):
            return {
                "status": True,
                "message": "Successfully connected to Cisco ISE Server",
            }

    except Exception as e:
        print(traceback.format_exc())
        return {
            "status": False,
            "message": f"Error connecting to ISE Server at url {ise_server['address']}.",
        }


def lookup_groups(ise_server, debug=False):
    """
    Retrive the Network Device Groups configured on the ISE Server

    :param ise_server: A dictionary {"address": "192.168.0.11", "username": "admin", "password": "password"}
    """

    ise = ERS(
        ise_node=ise_server["address"],
        ers_user=ise_server["username"],
        ers_pass=ise_server["password"],
        verify=False,
        disable_warnings=True,
        timeout=10,
    )

    # dictionary to hold groups
    ise_groups = {}

    # paging variables for lookup
    size, page = 20, 0
    while page == 0 or (response["total"] > page * size):
        page += 1
        if debug:
            print(f"Sending ise.get_device_groups(size = {size}, page = {page})")
        response = ise.get_device_groups(size=size, page=page)
        if response["success"]:
            if debug:
                print(response)
            for group in response["response"]:
                ise_groups[group[0]] = {"id": group[1], "description": group[2]}
        else:
            if debug:
                print(response)
            return False

    return ise_groups


def sync_groups(
    ise_server,
    current_groups,
    group_diff,
    description="",
    remove_extra=False,
    debug=False,
):
    """
    Sync the Network Device Groups configured on the ISE Server

    :param ise_server: A dictionary {"address": "192.168.0.11", "username": "admin", "password": "password"}
    :param current_groups: A dictionary of current ISE groups. {"group#name": {"id": "", "description": ""}}
    :param group_diff: A diff dictionary of group changes needed
        {
            "correct": set('group#name')},
            "incorrect": set('group#name')},
            "missing": set('group#name')},
            "extra": set('group#name')}
        }
    : param description: The description to apply to updated or created groups (default "")
    :return results dictionary
    """

    results = {"updated": {}, "created": {}, "deleted": {}}

    ise = ERS(
        ise_node=ise_server["address"],
        ers_user=ise_server["username"],
        ers_pass=ise_server["password"],
        verify=False,
        disable_warnings=True,
        timeout=10,
    )

    for group in group_diff["correct"]:
        if debug:
            print(f"Group {group} is correct. No changes to be made.")

    for group in group_diff["incorrect"]:
        if debug:
            print(f"Group {group} is incorrect. Updating group.")
        results["updated"][group] = ise.update_device_group(
            device_group_oid=current_groups[group]["id"], description=description
        )

    for group in group_diff["missing"]:
        if debug:
            print(f"Group {group} is missing. It will be created.")
        results["created"][group] = ise.add_device_group(
            name=group, description=description
        )

    if remove_extra:
        for group in group_diff["extra"]:
            if debug:
                print(f"Group {group} is 'extra'. It will be removed.")
            # results["deleted"][group] = ise.delete_device_group(name=group)

    else:
        if debug:
            print(f"remove_extra is {remove_extra}. Extra groups will be ignored")

    return results


def lookup_ise_devices(ise_server, debug=False):
    """
    Retrieve the Network Devices from ISE

    :param ise_server: A dictionary {"address": "192.168.0.11", "username": "admin", "password": "password"}
    :return a results dictionary with device name as key and ISE config as value
    """

    ise = ERS(
        ise_node=ise_server["address"],
        ers_user=ise_server["username"],
        ers_pass=ise_server["password"],
        verify=False,
        disable_warnings=True,
        timeout=10,
    )

    # dictionary to hold devices
    ise_devices = {}

    # paging variables for lookup
    size, page = 20, 0
    while page == 0 or (response["total"] > page * size):
        page += 1
        if debug:
            print(f"Sending ise.get_devices(size = {size}, page = {page})")
        response = ise.get_devices(size=size, page=page)
        if response["success"]:
            if debug:
                print(response)
            for device in response["response"]:
                if debug:
                    print(
                        f"Looking up network device details from ISE for device name {device[0]}"
                    )
                ise_device = ise.get_device(device=device[0])
                if debug:
                    print(ise_device)
                ise_devices[device[0]] = ise_device["response"]
        else:
            if debug:
                print(response)
            return False

    return ise_devices


def sync_devices(
    ise_server,
    devices_diff,
    remove_extra=False,
    debug=False,
):
    """
    Sync the Network Devices configured on the ISE Server

    :param ise_server: A dictionary {"address": "192.168.0.11", "username": "admin", "password": "password"}
    :param current_groups: A dictionary of current ISE groups. {"group#name": {"id": "", "description": ""}}
    :param devices_diff: A diff dictionary of device changes needed
        {
            "correct": {} },
            "incorrect": {} },
            "missing": {} },
            "extra": {} }
        }
    :return results dictionary
    """

    results = {"updated": {}, "created": {}, "deleted": {}}

    ise = ERS(
        ise_node=ise_server["address"],
        ers_user=ise_server["username"],
        ers_pass=ise_server["password"],
        verify=False,
        disable_warnings=True,
        timeout=10,
    )

    for device in devices_diff["correct"]:
        if debug:
            print(f"Device {device} is correct. No changes to be made.")

    for device, diff_details in devices_diff["incorrect"].items():
        if debug:
            print(f"Device {device} is incorrect. Updating device.")
        # Update the device using the current.name
        results["updated"][device] = ise.update_device(
            name=diff_details["current"]["name"], device_payload=diff_details["desired"]
        )
        if debug:
            print(results["updated"][device])

    for device, diff_details in devices_diff["missing"].items():
        if debug:
            print(f"Device {device} is missing. It will be created.")
        results["created"][device] = ise.add_device(
            device_payload=diff_details["desired"]
        )

    if remove_extra:
        for device in devices_diff["extra"]:
            if debug:
                print(f"Device {device} is 'extra'. It will be removed.")
            results["deleted"][device] = {}
            # results["deleted"][group] = ise.delete_device_group(name=group)

    else:
        if debug:
            print(f"remove_extra is {remove_extra}. Extra groups will be ignored")

    return results
