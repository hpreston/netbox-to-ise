#! /usr/bin/env python
"""
This is a command line tool used to keep Cisco ISE Servers in sync with a 
NetBox based source of truth. 
"""


import click
from os.path import dirname, realpath
from os import getenv
import yaml

from rich.console import Console
from rich.table import Table
from rich import print as rprint

from netbox2ise.utils.cli_utils import (
    test_datafile,
    get_desired_devices,
    lookup_current_ise_config,
    generate_desired_ise_config,
    diff_configs,
    print_group_diff,
    print_devices_diff,
    print_group_sync,
    print_devices_sync,
    get_module_by_version
)

# from netbox2ise.utils.netbox import lookup_nb_devices
from netbox2ise.utils.conversion import (
    ise_device_from_netbox,
    set_of_ise_groups,
    diff_ise_groups,
    diff_ise_devices,
)

console = Console()


@click.group()
def cli():
    """
    Use this tool to keep your Cisco ISE Network Devices and Network Device
    Groups synchronized.
    """
    pass


@click.command()
@click.option("--data-file", default=None, help="YAML datafile for netbox2ise")
@click.option(
    "--remove-extra",
    default=False,
    help="Whether to remove extra data in ISE that is NOT defined in NetBox",
)
@click.option(
    "--debug",
    default=False,
    type=click.BOOL,
    help="Whether to print debug messages from process.",
)
# @click.argument('name')
def sync(data_file, remove_extra, debug):
    """
    This command will lookup data from NetBox and generate the desired configuration
    for Cisco ISE to match the devices and vms returned. Cisco ISE will then be
    updated with the generated configuration.
    """
    click.echo("Synchronizing ISE with NetBox")

    datafile = test_datafile(data_file)
    if not datafile:
        rprint("[bold red]Error verifying data-file. Stopping process.")
        return

    # Import the correct ISE module based on the version
    ise = get_module_by_version(datafile["defaults"]["ise_server"]["version"])
    if not ise:
        rprint("[bold red]Unable to load ISE library. Stopping process.")
        return

    console.rule(f"[bold black] Calculating Diffs", align="left")

    # Get Current ISE Devices and Groups
    current_devices, current_groups = lookup_current_ise_config(
        datafile["defaults"]["ise_server"], debug=debug
    )

    # Get Desired ISE Devices and Groups
    # Create variables for desired devices and groups that will contain info from all jobs
    desired_devices = {}
    desired_groups = set()

    # Process each job in the jobs list from the data file
    for job in datafile["jobs"]:
        console.rule(
            f'[bold black]  * Working on job {job["name"]}',
            align="left",
        )
        job_desired_devices, job_desired_groups = generate_desired_ise_config(
            datafile["defaults"]["netbox_server"], job, debug
        )
        desired_devices.update(job_desired_devices)
        desired_groups.update(job_desired_groups)

    # Generate diffs
    devices_diff, groups_diff = diff_configs(
        current_devices=current_devices,
        desired_devices=desired_devices,
        current_groups=current_groups,
        desired_groups=desired_groups,
        desired_group_description="From NetBox SoT",
        debug=debug,
    )

    console.rule(f"[bold black] Syncing Network Device Groups", align="left")
    groups_sync = ise.sync_groups(
        datafile["defaults"]["ise_server"],
        current_groups,
        groups_diff,
        description="From NetBox SoT",
        debug=debug,
    )
    if debug:
        console.log(f"groups_sync: {groups_sync}")
    # Print the sync results table if there were updates made
    if (
        len(groups_sync["updated"].values())
        + len(groups_sync["created"].values())
        + len(groups_sync["deleted"].values())
        > 0
    ):
        print_group_sync(groups_sync)
    else:
        rprint("   [grey]No changes to Network Device Groups made.")

    console.rule(f"[bold black] Syncing Network Devices", align="left")
    devices_sync = ise.sync_devices(
        datafile["defaults"]["ise_server"], devices_diff, debug=debug
    )

    # Print the sync results table if there were updates made
    if (
        len(devices_sync["updated"].values())
        + len(devices_sync["created"].values())
        + len(devices_sync["deleted"].values())
        > 0
    ):
        print_devices_sync(devices_sync)
    else:
        rprint("   [grey]No changes to Network Devices made.")


@click.command()
@click.option("--data-file", default=None, help="YAML datafile for netbox2ise")
@click.option(
    "--display-group-diff",
    default=False,
    type=click.BOOL,
    help="Whether to print the group-diff table.",
)
@click.option(
    "--debug",
    default=False,
    type=click.BOOL,
    help="Whether to print debug messages from process.",
)
def verify(data_file, display_group_diff, debug):
    """
    This command will perform a verification check of Cisco ISE to see whether
    it is syncronized with NetBox. Where deviations are discovered, they will
    be reported.
    """
    click.echo("Verifying that ISE is insync with NetBox")

    datafile = test_datafile(data_file)
    if not datafile:
        rprint("[bold red]Error verifying data-file. Stopping process.")
        return

    console.rule(
        f'[bold black]Looking up Current Devices and Groups from ISE Server {datafile["defaults"]["ise_server"]["address"]}',
        align="left",
    )
    current_devices, current_groups = lookup_current_ise_config(
        datafile["defaults"]["ise_server"], debug=debug
    )

    console.rule(
        "[bold black]Generating Desired ISE Configuration from NetBox", align="left"
    )

    # Create variables for desired devices and groups that will contain info from all jobs
    desired_devices = {}
    desired_groups = set()

    # Process each job in the jobs list from the data file
    for job in datafile["jobs"]:
        console.rule(
            f'[bold black]* Building Desired Devices Configurations for job {job["name"]}',
            align="left",
        )
        job_desired_devices, job_desired_groups = generate_desired_ise_config(
            datafile["defaults"]["netbox_server"], job, debug
        )
        desired_devices.update(job_desired_devices)
        desired_groups.update(job_desired_groups)

    console.rule(
        f"[bold black]* Determining Diffs between Current and Desired Configurations",
        align="left",
    )
    devices_diff, groups_diff = diff_configs(
        current_devices=current_devices,
        desired_devices=desired_devices,
        current_groups=current_groups,
        desired_groups=desired_groups,
        desired_group_description="From NetBox SoT",
        debug=debug,
    )

    if display_group_diff:
        print_group_diff(groups_diff)

    print_devices_diff(devices_diff)


@click.command()
@click.option(
    "--output-file", default=None, help="File name to write the example datafile to."
)
def example_datafile(output_file):
    """
    This command will generate an example YAML data-file for use with netbox2ise. If no
    outputfile is provided, the example will be printed to the screen.
    """
    directory = dirname(realpath(__file__))

    with open(f"{directory}/files/datafile-example.yaml") as f:
        example = f.read()

    if output_file:
        print(f"Saving ")
        with open(output_file, "w") as f:
            f.write(example)
    else:
        print(example)


@click.command()
@click.argument("data-file", required=True)
def check_datafile(data_file):
    """
    This command will attempt to read the data-file and verify it has all required
    data for netbox2ise
    """

    verify_datafile = test_datafile(data_file)
    if not verify_datafile:
        rprint("[bold red]Error verifying data-file. Stopping process.")
        return


cli.add_command(sync)
cli.add_command(verify)
cli.add_command(example_datafile)
cli.add_command(check_datafile)
