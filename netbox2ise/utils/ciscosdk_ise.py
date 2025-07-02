"""
This is a set of Cisco ISE related functions used to retrieve and update data for ISE versions 3.1 and later
Uses the ciscoisesdk library
"""
from ciscoisesdk import IdentityServicesEngineAPI
import traceback


def verify_ise(ise_server):
    """
    Verify an ISE Server is reachable

    :param ise_server: A dictionary {"address": "192.168.0.11", "username": "admin", "password": "password"}
    :return status dictionary
    """

    ise = IdentityServicesEngineAPI(username=ise_server["username"],
                                password=ise_server["password"],
                                uses_api_gateway=True,
                                base_url=f"https://{ise_server['address']}",
                                version=ise_server['version'],
                                verify=False,
                                debug=True)

    try:
        # Get all network devices to verify authentication works correctly
        devices = ise.network_device.get_all().response.SearchResult.resources

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

    ise = IdentityServicesEngineAPI(username=ise_server["username"],
                                password=ise_server["password"],
                                uses_api_gateway=True,
                                base_url=f"https://{ise_server['address']}",
                                version=ise_server['version'],
                                verify=False,
                                debug=True)

    # dictionary to hold groups
    ise_groups = {}

    # paging variables for lookup
    size, page = 20, 0
    while page == 0 or (search_result["total"] > page * size):
        page += 1
        if debug:
            print(f"Sending ise.get_device_groups(size = {size}, page = {page})")

        search_result =  ise.network_device_group.get_all(size=size, page=page).response.SearchResult
        if search_result:
            if debug:
                print(search_result)
            for group in search_result.resources:
                ise_groups[group.name] = {"id": group.id, "description": group.description}
        else:
            if debug:
                print(search_result)
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

    ise = IdentityServicesEngineAPI(username=ise_server["username"],
                                password=ise_server["password"],
                                uses_api_gateway=True,
                                base_url=f"https://{ise_server['address']}",
                                version=ise_server['version'],
                                verify=False,
                                debug=True)

    for group in group_diff["correct"]:
        if debug:
            print(f"Group {group} is correct. No changes to be made.")

    for group in group_diff["incorrect"]:
        if debug:
            print(f"Group {group} is incorrect. Updating group.")

        results["updated"][group] = ise.network_device_group.update_network_device_group_by_id(
            id=current_groups[group]['id'], description=description, name=group, othername=group.split("#")[0]
        )
        
    for group in group_diff["missing"]:
        if debug:
            print(f"Group {group} is missing. It will be created.")

        results["created"][group] = ise.network_device_group.create_network_device_group(
            name=group, description=description, othername=group.split("#")[0]
        )
    remove_extra = True
    if remove_extra:
        for group in group_diff["extra"]:
            if debug:
                print(f"Group {group} is 'extra'. It will be removed.")
            
            #results["deleted"][group] = ise.network_device_group.delete_network_device_group_by_id(id=current_groups[group]["id"])

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

    ise = IdentityServicesEngineAPI(username=ise_server["username"],
                                password=ise_server["password"],
                                uses_api_gateway=True,
                                base_url=f"https://{ise_server['address']}",
                                version=ise_server['version'],
                                verify=False,
                                debug=True)

    # dictionary to hold devices
    ise_devices = {}

    # paging variables for lookup
    size, page = 20, 0
    while page == 0 or (search_result["total"] > page * size):
        page += 1
        if debug:
            print(f"Sending ise.get_devices(size = {size}, page = {page})")
        
        search_result = ise.network_device.get_all(size=size, page=page).response.SearchResult

        if search_result:
            if debug:
                print(search_result)

            for device in search_result.resources:
                if debug:
                    print(
                        f"Looking up network device details from ISE for device name {device.name}"
                    )
                ise_device = ise.network_device.get_network_device_by_name(name=device.name)

                if debug:
                    print(ise_device.response)
                if ise_device.response and ise_device.response.NetworkDevice:
                    ise_devices[device.name] = ise_device.response.NetworkDevice
        else:
            if debug:
                print(search_result)
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

    ise = IdentityServicesEngineAPI(username=ise_server["username"],
                                password=ise_server["password"],
                                uses_api_gateway=True,
                                base_url=f"https://{ise_server['address']}",
                                version=ise_server['version'],
                                verify=False,
                                debug=True)

    for device in devices_diff["correct"]:
        if debug:
            print(f"Device {device} is correct. No changes to be made.")

    for device, diff_details in devices_diff["incorrect"].items():
        if debug:
            print(f"Device {device} is incorrect. Updating device.")
        # Update the device using the current.name
        results["updated"][device] = ise.network_device.update_network_device_by_name(
            name=diff_details["current"]["name"],
            description=diff_details["desired"]["description"],
            profile_name=diff_details["desired"]["profileName"],
            coa_port=diff_details["desired"]["coaPort"],
            network_device_iplist=diff_details["desired"]["NetworkDeviceIPList"],
            network_device_group_list=diff_details["desired"]["NetworkDeviceGroupList"],
            tacacs_settings=diff_details["desired"].get("tacacsSettings"),
            authentication_settings=diff_details["desired"].get("authenticationSettings"),
        ).response

        if debug:
            print(results["updated"][device])

    for device, diff_details in devices_diff["missing"].items():
        if debug:
            print(f"Device {device} is missing. It will be created.")

        response = ise.network_device.create_network_device(
            name=diff_details["desired"]["name"],
            description=diff_details["desired"]["description"],
            profile_name=diff_details["desired"]["profileName"],
            coa_port=diff_details["desired"]["coaPort"],
            network_device_iplist=diff_details["desired"]["NetworkDeviceIPList"],
            network_device_group_list=diff_details["desired"]["NetworkDeviceGroupList"],
            tacacs_settings=diff_details["desired"].get("tacacsSettings"),
            authentication_settings=diff_details["desired"].get("authenticationSettings"),
        )
        
        # Adding a device successfully returns a 201 (Created) status code, with no response body
        # Add the response to the results dictionary that the device was added successfully
        if response.status_code == 201:
            results["created"][device] = {"success": True, "response": f"{device} Added Successfully"}
        else:
            results["created"][device] = {"success": False, "response": f"Error {device} Adding Device: {response.response}"}

    if remove_extra:
        for device, diff_details in devices_diff["extra"].items():
            if debug:
                print(f"Device {device} is 'extra'. It will be removed.")
            results["deleted"][device] = {}

    else:
        if debug:
            print(f"remove_extra is {remove_extra}. Extra groups will be ignored")

    return results
