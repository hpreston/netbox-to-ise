# `netbox2ise` - Keeping your Cisco ISE Environment in sync with a NetBox Source of Truth

This project aims to use NetBox as a Source of Truth for ISE Network Devices and Network Device Group Membership.

## Table of Contents

* [Mapping NetBox Attributes to ISE](#mapping-netbox-attributes-to-ise)
* [Installing netbox2ise](#installing-netbox2ise)
* [TL:DR - Getting Started Quickly](#tldr-getting-started-quickly)

### Other Documents 

* [netbox2ise "architecture" overview (`netbox2ise-architecture.md`)](netbox2ise-architecture.md)

## Mapping NetBox Attributes to ISE
As a Source of Truth, NetBox uses many fields to organize devices that can be used within ISE for similar organization.  Here is how the fields will map together.  

| NetBox Field | ISE Field | Notes | 
| ------------ | --------- | ----- | 
| Site | A Location Group |  | 
| Rack | A Location Group UNDER the Site Group | Devices without a RACK assignment will use their Site Location Group | 
| Cluster | A Location Group UNDER the Site Group | Clusters without a SITE assignment will be created under top level Locations. (Note: Clusters used for VM locations) |
| Manufacturer | A Device Type Group | This ISE Group will be used as Parent for explicit Device Types | 
| Device Type | A Device Type Group UNDER the Manufacturer | | 
| Device Role | A root group of **Device Role** will be created to organize Device Roles | Relevant for VM Roles as well | 
| Tenant Group | A root group for **Tenant** will be created to organize Tenants and Tenant Groups | Tenants without groups will be created directly under the root **Tenant** group | 
| Device Name | ISE Device Name | | 
| Device Primary IP | ISE IP Address and Mask | This project will enforce/assume a single IP address for a device | 

## Installing netbox2ise 
In its current state, `netbox2ise` requires the following steps to install and use. 

1. Clone down this repo to your workstation and move into the directory
1. Create and activate a Python Virtual Environment to work within.  Python 3.8 is recommended, though other versions may work. 

    ```shell
    python3.8 -m venv venv
    source venv/bin/activate
    ```

1. Install the Python requirements from [`requirements.txt`](requirements.txt)

    ```shell
    pip install -r requirements.txt
    ```

    > Note: `netbox2ise` uses a public Python ISE library (https://github.com/falkowich/pyise-ers). The `requirements.txt` file reflects this source for the library. 

1. Install the `netbox2ise` tool. 

    ```shell
    python setup.py install 
    ```

## TL:DR - Getting Started Quickly 
We will dive into details on how the tool works under the hood, but let's start with a simple look at how to use it.  For this discussion the following assumptions are made. 

1. You already have a Cisco ISE server setup.  
    * It has the ERS APIs enabled, and you have an ERS Admin user to work with. 
2. You already have your NetBox server setup.  
    * You have an API token with at least READ permissions available 
    * There are devices and virtual machines defined within NetBox that you'd like to have added to ISE
        
        > Note: See [Caveats and Important Info](#caveats-and-important-info) for details on requirements/expectations of how NetBox devices/vms are configured.

### Defining your `datafile.yaml` 
The `netbox2ise` tool requires a YAML based `datafile` that defines the Cisco ISE and NetBox server, as well as 1 or more sync `job` definitions.  You can generate an example/default `datafile.yaml` with the command. 

```bash
netbox2ise example-datafile 
```

> Note: You can provide the argument `--output-file FILENAME.YAML` to write the output to a file rather than the screen

***output***

```yaml
# Example datafile for syncing NetBox and Cisco ISE 
defaults: 
  netbox_server: 
    url: http://netbox.exmaple.local
    # If no token is provided or if it is false, an ENV of NETBOX_TOKEN will be looked for
    token: nadkafniadkafnakdandakdnadkadnadks  
  ise_server: 
    address: ise.example.local  # or an IP address
    # If no username is provided or if it is false, an ENV of ISE_USER will be looked for
    username: false
    # If no password is provided or if it is false, an ENV of ISE_PASS will be looked for
    password: false
  # The underlying functions within netbox2ise have debug outputs that display data. Set to True to display these
  debug: false

# A list of sync jobs with relevant data for syncronizing 
jobs:
- name: primary 
  # The fields provided here will determine what devices and vms from NetBox are discovered
  netbox_query: 
    # Site Names
    sites: 
    - Site01
    # NetBox Tenants to filter on 
    tenants: 
    - admin
    - mgmt 
    # Device and VM Status to filter on
    status: 
    - active 
    - staged
    # Model Names for each Device Type to find 
    device_types: 
    - Nexus 9300v
    - ASAv
    # Device Role Names for each Device or VM Role to find 
    device_roles: 
    - Switch
    - Firewall
  # Configuration settings to apply to returned devices in this job
  #   Not providing configuration for TACACS or RADIUS will result in that protocol being left unconfigured
  ise_config: 
    tacacs: 
      secret: MySecret99
    radius: 
      secret: MySecret100
```

If you review the output, you'll see the file setup is pretty straightforward.  Simply create a file from this example with your data.

Here is another exmaple datafile 

```yaml
# Data for syncing NetBox and Cisco ISE 
defaults: 
  netbox_server: 
    url: http://192.168.10.101
    token: false 
  ise_server: 
    address: 192.168.10.102
    username: false
    password: false

jobs:
- name: demo 
  netbox_query: 
    sites: 
    - TST01 
    device_types: 
    - CSR 1000v-physical
    device_roles: 
    - Virtual/Physical Router
  ise_config: 
    tacacs: 
      secret: d3m0t@c@$
```

Notice how the token, username, and password fields for NetBox and ISE are set to `false`.  This means we must set ENV for these values. 

```bash
export ISE_USER=ersadmin
export ISE_PASS=SuperSecret 
export NETBOX_TOKEN=nakasdinad9a7sinadkad9ndaks
```

To do a final check that your datafile setup is working, run the `check-datafile` command. 

```shell
netbox2ise check-datafile demo-datafile.yaml 

Checking NetBox and ISE Servers ───────────────────────────────────────────────────────────────────
NetBox Server http://192.168.10.101 successfully connected to.
ISE Server 192.168.10.102 successfully connected to.
```


### Running a Verification Check 
With your datafile generated, you can now run a `verify` check to see what your current sync state is. 

```shell
netbox2ise verify --data-file demo-datafile.yaml 
```

This will provide output that looks like this

```shell
Verifying that ISE is insync with NetBox
Checking NetBox and ISE Servers ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
NetBox Server http://tst01-z0-vm-netbox-01 successfully connected to.
ISE Server tst01-z0-vm-ise-01 successfully connected to.
Looking up Current Devices and Groups from ISE Server tst01-z0-vm-ise-01 ──────────────────────────────────────────────────────────────────────
Generating Desired ISE Configuration from NetBox ──────────────────────────────────────────────────────────────────────────────────────────────
* Building Desired Devices Configurations for job demo ────────────────────────────────────────────────────────────────────────────────────────
* Determining Diffs between Current and Desired Configurations ────────────────────────────────────────────────────────────────────────────────
                                                          Network Device Differences                                                           
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Device Name          ┃ Status    ┃ Field Changes                                      ┃ Network Device Groups                               ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ tst01-z0-rtr-dmz-01  │ correct   │                                                    │                                                     │
├──────────────────────┼───────────┼────────────────────────────────────────────────────┼─────────────────────────────────────────────────────┤
│ tst01-z0-rtr-edge-01 │ incorrect │ root['NetworkDeviceIPList'][0]['ipaddress']        │ correct                                             │
│                      │           │   from 10.224.128.99                               │  - Location#All Locations#TST01                     │
│                      │           │   to 10.224.128.13                                 │  - IPSEC#Is IPSEC Device#No                         │
│                      │           │                                                    │  - Device Type#All Device Types#Cisco#CSR           │
│                      │           │                                                    │ 1000v-physical                                      │
│                      │           │                                                    │  - Tenant#Tenant#tst01-z0#tst01-z0-admin            │
│                      │           │                                                    │ missing                                             │
│                      │           │                                                    │  - Device Role#Device Role#Virtual-Physical Router  │
│                      │           │                                                    │ extra                                               │
│                      │           │                                                    │  - Device Role#Device Role#Virtual Router           │
├──────────────────────┼───────────┼────────────────────────────────────────────────────┼─────────────────────────────────────────────────────┤
│ tst01-z0-rtr-dmz-02  │ missing   │ name: tst01-z0-rtr-dmz-02                          │ missing                                             │
│                      │           │ description: From NetBox:                          │  - Location#All Locations#TST01                     │
│                      │           │ http://tst01-z0-vm-netbox-01/api/dcim/devices/206/ │  - IPSEC#Is IPSEC Device#No                         │
│                      │           │ profileName: Cisco                                 │  - Tenant#Tenant#tst01-z0#tst01-z0-admin            │
│                      │           │ coaPort: 1700                                      │  - Device Type#All Device Types#Cisco#CSR           │
│                      │           │ NetworkDeviceIPList: [{'ipaddress':                │ 1000v-physical                                      │
│                      │           │ '10.224.128.22', 'mask': 32}]                      │  - Device Role#Device Role#Virtual-Physical Router  │
│                      │           │ tacacsSettings: {'sharedSecret': 'd3m0t@c@$',      │                                                     │
│                      │           │ 'connectModeOptions': 'ON_LEGACY'}                 │                                                     │
├──────────────────────┼───────────┼────────────────────────────────────────────────────┼─────────────────────────────────────────────────────┤
│ tst01-z0-rtr-edge-02 │ missing   │ name: tst01-z0-rtr-edge-02                         │ missing                                             │
│                      │           │ description: From NetBox:                          │  - Location#All Locations#TST01                     │
│                      │           │ http://tst01-z0-vm-netbox-01/api/dcim/devices/202/ │  - IPSEC#Is IPSEC Device#No                         │
│                      │           │ profileName: Cisco                                 │  - Tenant#Tenant#tst01-z0#tst01-z0-admin            │
│                      │           │ coaPort: 1700                                      │  - Device Type#All Device Types#Cisco#CSR           │
│                      │           │ NetworkDeviceIPList: [{'ipaddress':                │ 1000v-physical                                      │
│                      │           │ '10.224.128.14', 'mask': 32}]                      │  - Device Role#Device Role#Virtual-Physical Router  │
│                      │           │ tacacsSettings: {'sharedSecret': 'd3m0t@c@$',      │                                                     │
│                      │           │ 'connectModeOptions': 'ON_LEGACY'}                 │                                                     │
└──────────────────────┴───────────┴────────────────────────────────────────────────────┴─────────────────────────────────────────────────────┘
```

The table will indicate which devices from NetBox are `correct`, `incorrect`, or `missing` from Cisco ISE.  And details on field changes and group changes needed to bring them in sync will be displayed.  

### Running a Sync 
If you'd like to update Cisco ISE based on the data in NetBox, simply run a `sync` job. 

```shell
netbox2ise sync --data-file demo-datafile.yaml 
```

And the output

```shell
Synchronizing ISE with NetBox
Checking NetBox and ISE Servers ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
NetBox Server http://tst01-z0-vm-netbox-01 successfully connected to.
ISE Server tst01-z0-vm-ise-01 successfully connected to.
 Calculating Diffs ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
  * Working on job demo ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
 Syncing Network Device Groups ────────────────────────────────────────────────────────────────────────────────────────────────────────────────
   No changes to Network Device Groups made.
 Syncing Network Devices ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
                                                         Network Devices Sync Results                                                          
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Device Name          ┃ Status  ┃ Results                                                                                                    ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ tst01-z0-rtr-edge-01 │ updated │ Field Description was "From NetBox: http://tst01-z0-vm-netbox-01/api/dcim/devices/201/" now "From NetBox:  │
│                      │         │ http://tst01-z0-vm-netbox-01/api/dcim/devices/201/"                                                        │
│                      │         │ Field NetworkDeviceGroupList was "item removed: Name:Device Role#Device Role#Virtual Router ,Type:Device   │
│                      │         │ Role, NSF REF: 1b3630b0-a784-11eb-ac01-36750594a888"                                                       │
│                      │         │ Field NetworkDeviceGroupList now "item added: Name:Device Role#Device Role#Virtual-Physical Router         │
│                      │         │ ,Type:Device Role, NSF REF: 1a9535c0-a784-11eb-ac01-36750594a888"                                          │
│                      │         │ Field NetworkDeviceIpList was "item removed: IP:10.224.128.99 , Mask:32 , Min:182485091, Max: 182485091"   │
│                      │         │ Field NetworkDeviceIpList now "item added: IP:10.224.128.13 , Mask:32 , Min:182485005, Max: 182485005"     │
├──────────────────────┼─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ tst01-z0-rtr-dmz-02  │ created │ tst01-z0-rtr-dmz-02 Added Successfully                                                                     │
├──────────────────────┼─────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ tst01-z0-rtr-edge-02 │ created │ tst01-z0-rtr-edge-02 Added Successfully                                                                    │
└──────────────────────┴─────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

The output from the sync job will show you which devices were `created` or `updated`, as well as details on results.  For any `updated` devices, specific messages from ISE on the changes made to the device will be shown.  

## Caveats and Important Info
### NetBox Devices and Virtual Machine requirements 
In order for network devices to be setup in Cisco ISE correctly based on NetBox definitions, the following characteristics are mandatory. 

* The device or vm ***MUST*** have a primary ip address identified.  This IP address will be configured as the IP address for the device within Cisco ISE
* All Virtual Machines are configured with a Device Type in ISE of `Device Types#All VMs#General VM` as NetBox doesn't have a `Device Type` attribute for VMs
* VM Roles within NetBox should be assigned to VMs to provide an attribute that can be used in Cisco ISE as a `Network Device Group` for uniquely identifying groups of VMs 

