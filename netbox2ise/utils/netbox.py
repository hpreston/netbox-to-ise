"""
This is a set of NetBox related functions used to retrieve data from NetBox
"""

import pynetbox
from requests import exceptions
from pynetbox.core.query import RequestError


def verify_netbox(netbox_server):
    """
    Verify a NetBox Server is reachable

    :param netbox_server: A dictionary {"url": "http://netbox.address.local", "token": "API Token"}
    :return status dictionary
    """
    nb = pynetbox.api(netbox_server["url"], token=netbox_server["token"])
    try:
        status = nb.status()
    except RequestError as e:
        # Older versions of NetBox don't have the status api, try to retrieve devices
        devices = nb.dcim.devices.all()
        return {
            "status": True,
            "message": f"Successfully connected to NetBox to query devices.",
        }
    except exceptions.ConnectionError:
        return {
            "status": False,
            "message": f"Error connecting to NetBox Server at url {netbox_server.url}.",
        }

    status_message = f"NetBox Version: {status['netbox-version']}, Python Version: {status['python-version']}, Plugins: {status['plugins']}, Workers Running: {status['rq-workers-running']}"
    return {"status": True, "message": status_message}


def query_netbox(object, debug=False, **query):
    """
    Generic function to send a filter query to NetBox for an object

    :param object: A reference to a pynetbox object. Example nb.dcim.device_types
    :param **query: A dictionary of key/values to filter results
    :return results from NetBox
    """
    if query == {}:
        results = object.all()
    else:
        results = object.filter(**query)
    if debug:
        print(f"Results: {results}")

    # Note: Converting the returned `RecordSet` to a list to support code that
    # loops over and access the returned set of data more than once.
    return list(results)


def lookup_nb_devices(
    netbox_server,
    sites=[],
    device_types=[],
    device_roles=[],
    tenants=[],
    status=[],
    has_primary_ip="True",
    debug=False,
):
    """
    Lookup devices and vms from NetBox given a set of filter conditions.

    :param netbox_server: A dictionary {"url": "http://netbox.address.local", "token": "API Token"}
    :param sites: A list of Site Names to lookup in NetBox
    :param device_types: A list of Device Type Models to lookup in NetBox
    :param device_roles: A list of Device Role Names to lookup in NetBox
    :param tenants: A list of Tenant Names to lookup in Netbox
    :param has_primary_ip: A boolean to limit result based on if primary_ip assigned (default True)

    :return results list
    """

    try:
        nb = pynetbox.api(netbox_server["url"], token=netbox_server["token"])

        device_query = {}
        vm_query = {}

        if len(sites) > 0:
            sites = query_netbox(
                object=nb.dcim.sites, debug=debug, name=[site for site in sites]
            )
            device_query["site_id"] = [site.id for site in sites]
            vm_query["site_id"] = [site.id for site in sites]

        if len(device_types) > 0:
            device_types = query_netbox(
                object=nb.dcim.device_types,
                debug=debug,
                model=[device_type for device_type in device_types],
            )
            device_query["device_type_id"] = [
                device_type.id for device_type in device_types
            ]

        if len(device_roles) > 0:
            device_roles = query_netbox(
                object=nb.dcim.device_roles,
                debug=debug,
                name=[device_role for device_role in device_roles],
            )
            device_query["role_id"] = [device_role.id for device_role in device_roles]
            vm_roles = query_netbox(
                object=nb.dcim.device_roles,
                debug=debug,
                name=[device_role for device_role in device_roles],
                vm_role=True,
            )
            vm_query["role_id"] = [vm_role.id for vm_role in vm_roles]

        if len(tenants) > 0:
            tenants = query_netbox(
                object=nb.tenancy.tenants,
                debug=debug,
                name=[tenant for tenant in tenants],
            )
            device_query["tenant_id"] = [tenant.id for tenant in tenants]
            vm_query["tenant_id"] = [tenant.id for tenant in tenants]

        if len(status) > 0:
            device_query["status"] = status
            vm_query["status"] = status

        device_query["has_primary_ip"] = has_primary_ip
        vm_query["has_primary_ip"] = has_primary_ip

        if debug:
            print(f"device_query: {device_query}")
            print(f"vm_query: {vm_query}")

        devices = query_netbox(object=nb.dcim.devices, debug=debug, **device_query)
        # Only query VMs if at least one role is listed
        if len(vm_query["role_id"]) > 0:
            vms = query_netbox(
                object=nb.virtualization.virtual_machines, debug=debug, **vm_query
            )
        else:
            if debug:
                print("No VM roles were identified, skipping looking up VMs.")
            vms = {}

        return {"status": True, "devices": devices, "vms": vms}
    except Exception as e:
        if debug:
            print(f"Lookup failed: {e}")
        return {"status": False, "result": e}


if __name__ == "__main__":
    from os import environ

    netbox_server = {
        "url": environ.get("NETBOX_URL"),
        "token": environ.get("NETBOX_TOKEN"),
    }

    devices_a = lookup_devices(netbox_server, debug=True, sites=["TST01"])
    device_b = lookup_devices(
        netbox_server,
        debug=True,
        device_types=["Nexus 9300v", "Nexus 9500v", "ASAv-physical"],
    )
    device_c = lookup_devices(
        netbox_server,
        debug=True,
        device_roles=[
            "Virtual/Physical Firewall",
            "Virtual/Physical Switch",
            "Virtual/Physical Router",
        ],
    )
    device_d = lookup_devices(netbox_server, debug=True, tenants=["tst01-z0-admin"])
