import os

import arrow
import click
import requests

from .api import LAYOUT_DATE_FIELDS, login
from .data import LAYOUT_ALIASES, extract_data
from .output import html_output, text_output


@click.group()
@click.option("--server", required=True, type=str, default=lambda: os.environ.get("ICARE_SERVER", None))
@click.option("--username", required=True, type=str, default=lambda: os.environ.get("ICARE_USERNAME", None))
@click.option("--password", required=True, type=str, default=lambda: os.environ.get("ICARE_PASSWORD", None))
@click.pass_context
def cli(ctx, server, username, password):
    ctx.ensure_object(dict)
    ctx.obj["server"] = server
    ctx.obj["username"] = username
    ctx.obj["password"] = password


@cli.command()
@click.pass_context
def layouts(ctx):
    server = ctx.obj["server"]
    username = ctx.obj["username"]
    password = ctx.obj["password"]

    with requests.session() as session:
        token = login(session, server, username, password)
        session.headers["Authorization"] = f"Bearer {token}"
        url = f"{server}/fmi/data/vLatest/databases/iCareMobileAccess/layouts"
        r = session.get(url)
        r.raise_for_status()
        layout_names = [layout["name"] for layout in r.json()["response"]["layouts"][0]["folderLayoutNames"]]
        print("\n".join(layout_names))


@cli.command()
@click.pass_context
@click.option("--child-id", required=True, type=int, default=lambda: os.environ.get("ICARE_CHILD_ID", None))
@click.option("--child-name", type=str)
@click.option("--date", type=str, default="today")
@click.option("--limit", type=int)
@click.option(
    "--output-format",
    type=click.Choice(["text", "html"]),
    default=lambda: os.environ.get("ICARE_OUTPUT_FORMAT", "text"),
)
@click.option("--html-dir", type=str, default=".")
@click.argument("section", nargs=-1)
def report(ctx, child_id, child_name, date, limit, output_format, html_dir, section):
    server = ctx.obj["server"]
    username = ctx.obj["username"]
    password = ctx.obj["password"]
    if not child_name:
        child_name = str(child_id)

    if date and date == "today":
        date = arrow.now().format("MM/DD/YYYY")

    section_data = {}
    with requests.session() as session:
        for s in section:
            layout = LAYOUT_ALIASES.get(s)
            token = login(session, server, username, password)
            session.headers["Authorization"] = f"Bearer {token}"
            url = f"{server}/fmi/data/vLatest/databases/iCareMobileAccess/layouts/{layout}/_find"
            params = {
                "query": [
                    {
                        "child::childId": child_id,
                    }
                ],
            }
            if date:
                date_field = LAYOUT_DATE_FIELDS.get(layout)
                if date_field:
                    params["query"][0][date_field] = date
            if limit:
                params["limit"] = limit
            r = session.post(url, json=params)
            if r.json()["messages"][0]["code"] == "0":
                section_data[s] = extract_data(r.json(), s)
            else:
                print("Got error when downloading records")

    if output_format == "text":
        text_output(section_data)
    else:
        html_output(section_data, output_dir=html_dir, child_name=child_name, date=date)
