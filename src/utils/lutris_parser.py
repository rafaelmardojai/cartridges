# lutris_parser.py
#
# Copyright 2022-2023 kramo
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from shutil import copyfile
from sqlite3 import connect
from time import time


def lutris_parser(parent_widget):

    schema = parent_widget.schema

    database_path = (Path(schema.get_string("lutris-location"))).expanduser()
    if not database_path.exists():
        if Path("~/.var/app/net.lutris.Lutris/data/lutris/").expanduser().exists():
            schema.set_string(
                "lutris-location", "~/.var/app/net.lutris.Lutris/data/lutris/"
            )
        elif (parent_widget.data_dir / "lutris").exists():
            schema.set_string("lutris-location", str(parent_widget.data_dir / "lutris"))
        else:
            return

    cache_dir = Path(schema.get_string("lutris-cache-location")).expanduser()
    if not cache_dir.exists():
        if Path("~/.var/app/net.lutris.Lutris/cache/lutris/").expanduser().exists():
            schema.set_string(
                "lutris-cache-location", "~/.var/app/net.lutris.Lutris/cache/lutris/"
            )
        elif (parent_widget.cache_dir / "lutris").exists():
            schema.set_string(
                "lutris-cache-location", str(parent_widget.cache_dir / "lutris")
            )
        else:
            return

    database_path = (Path(schema.get_string("lutris-location"))).expanduser()
    cache_dir = Path(schema.get_string("lutris-cache-location")).expanduser()

    db_cache_dir = parent_widget.cache_dir / "cartridges" / "lutris"
    db_cache_dir.mkdir(parents=True, exist_ok=True)

    # Copy the file because sqlite3 doesn't like databases in /run/user/
    database_tmp_path = db_cache_dir / "pga.db"

    for db_file in database_path.glob("pga.db*"):
        copyfile(db_file, (db_cache_dir / db_file.name))

    db_request = """
                SELECT
                    id, name, slug, runner, hidden
                FROM
                    'games'
                WHERE
                    name IS NOT NULL
                    AND slug IS NOT NULL
                    AND configPath IS NOT NULL
                    AND installed IS TRUE
                ;
            """

    connection = connect(database_tmp_path)
    cursor = connection.execute(db_request)
    rows = cursor.fetchall()
    connection.close()
    # No need to unlink temp files as they disappear when the connection is closed
    database_tmp_path.unlink(missing_ok=True)

    if not schema.get_boolean("lutris-import-steam"):
        rows = [row for row in rows if not row[3] == "steam"]

    current_time = int(time())

    importer = parent_widget.importer
    importer.total_queue += len(rows)
    importer.queue += len(rows)

    for row in rows:
        values = {}

        values["game_id"] = f"lutris_{row[3]}_{row[0]}"

        if (
            values["game_id"] in parent_widget.games
            and not parent_widget.games[values["game_id"]].removed
        ):
            importer.save_game()
            continue

        values["added"] = current_time
        values["executable"] = ["xdg-open", f"lutris:rungameid/{row[0]}"]
        values["hidden"] = row[4] == 1
        values["last_played"] = 0
        values["name"] = row[1]
        values["source"] = f"lutris_{row[3]}"

        image_path = cache_dir / "coverart" / f"{row[2]}.jpg"
        importer.save_game(values, image_path if image_path.exists() else None)
