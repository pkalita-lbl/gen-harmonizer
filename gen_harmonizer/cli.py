import click
import subprocess
import json
import os
from pathlib import Path
from linkml_runtime.dumpers.json_dumper import JSONDumper
from linkml_runtime.utils.schemaview import SchemaView
from PyInquirer import prompt
from jinja2 import Environment, PackageLoader, select_autoescape

DH_INTERFACE = "dh_interface"


def err(message):
    click.echo(click.style(message, fg="red"))
    exit(1)


@click.command()
@click.argument("schema")
@click.argument(
    "dest",
    type=click.Path(
        file_okay=False, dir_okay=True, writable=True, resolve_path=True, path_type=Path
    ),
)
def run(schema: list[str], dest: Path):
    schema_view = SchemaView(schema)
    schema_view.merge_imports()
    # Materialize class slots from schema as attributes, in place
    all_classes = schema_view.all_classes()
    for c_name, c_def in all_classes.items():
        attrs = schema_view.class_induced_slots(c_name)
        for attr in attrs:
            c_def.attributes[attr.name] = attr

    answers = prompt(
        [
            {
                "type": "input",
                "message": "What would you like your new project to be called?",
                "name": "project_name",
                "default": dest.name,
            },
            {
                "type": "checkbox",
                "message": "The following classes were found in the provided schema. Which should be used as DataHarmonizer templates?",
                "name": "classes",
                "choices": [
                    {
                        "name": name,
                        "checked": DH_INTERFACE in schema_view.class_ancestors(name),
                    }
                    for name in schema_view.all_classes().keys()
                    if name is not DH_INTERFACE
                ],
            },
        ]
    )

    if not answers["classes"]:
        err("No classes selected. Project will not be generated.")

    env = Environment(
        loader=PackageLoader("gen_harmonizer"), autoescape=select_autoescape()
    )
    schema_name = schema_view.schema.name
    ctx = {"project_name": answers["project_name"], "schema_name": schema_name}

    dest.mkdir(parents=True, exist_ok=True)
    for name in env.list_templates():
        tpl = env.get_template(name)
        fname = str(os.path.splitext(tpl.name)[0])
        dest_file = dest / fname
        dest_file.parent.mkdir(exist_ok=True, parents=True)
        with open(dest / fname, "w") as out:
            out.write(tpl.render(ctx))

    schemas_dir = dest / "src/schemas"
    schemas_dir.mkdir()
    JSONDumper().dump(schema_view.schema, str(schemas_dir / f"{schema_name}.json"))

    menu = {
        schema_name: {
            class_name: {"name": class_name, "status": "published", "display": True}
            for class_name in answers["classes"]
        }
    }

    with open(schemas_dir / "_menu.json", "w") as fmenu:
        json.dump(menu, fp=fmenu, indent=2)

    try:
        subprocess.run(["npm", "install"], cwd=dest, check=True)
    except subprocess.CalledProcessError:
        try:
            subprocess.run(["which", "npm"], cwd=dest, check=True)
            err(f"Unable to run `npm install` in {dest}")
        except subprocess.CalledProcessError:
            err(f"Could not find `npm`. You may need to install Node.js.")

    click.echo(
        click.style(
            f"\n\n{answers['project_name']} successfully generated!",
            fg="green",
            bold=True,
        )
    )
    click.echo(
        click.style(
            f"""
You may now run:

  cd {dest}
  npm start

to begin using the new interface now. 
""",
            fg="green",
        )
    )


if __name__ == "__main__":
    run()
