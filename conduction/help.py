# Copyright © 2019-present gsfernandes81

# This file is part of "conduction-tines".

# conduction-tines is free software: you can redistribute it and/or modify it under the
# terms of the GNU Affero General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later version.

# "conduction-tines" is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
# PARTICULAR PURPOSE. See the GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License along with
# conduction-tines. If not, see <https://www.gnu.org/licenses/>.

import logging
import typing as t

import hikari as h
import lightbulb as lb
from lightbulb import commands, context as context_, plugins
import miru as m

from roman import toRoman as to_roman
from miru.ext import nav
from miru.ext.nav.items import NavButton

from . import cfg


class NumberedButton(nav.NavButton):
    """
    A built-in NavButton to jump to the next page.
    """

    def __init__(
        self,
        *,
        page_number,
        style: t.Union[h.ButtonStyle, int] = h.ButtonStyle.PRIMARY,
        label: t.Optional[str] = None,
        custom_id: t.Optional[str] = None,
        emoji: t.Union[h.Emoji, str, None] = None,
        row: t.Optional[int] = None,
    ):
        self.page_number = page_number
        super().__init__(
            style=style,
            label=label or str(page_number),
            custom_id=custom_id,
            emoji=emoji,
            row=row,
        )

    async def callback(self, context: m.ViewContext) -> None:
        self.view.current_page = self.page_number
        await self.view.send_page(context)

    async def before_page_change(self) -> None:
        if self.view.current_page == self.page_number:
            self.disabled = True
        else:
            self.disabled = False


def command_group_size(
    cmds_dict: t.Dict[str, lb.SlashCommand | lb.SlashGroupMixin],
    include_hidden: bool = True,
) -> int:
    count = 0

    for cmd in cmds_dict.values():
        cmd: lb.SlashCommand | lb.SlashGroupMixin

        if cmd.hidden and not include_hidden:
            continue

        try:
            cmd.subcommands
        except AttributeError:
            count += 1
        else:
            count += command_group_size(cmd.subcommands, include_hidden)

    return count


def regroup_commands(
    cmds_dict: t.Dict[str, lb.SlashCommand | lb.SlashCommandGroup]
) -> t.Dict[str, lb.SlashCommand | lb.SlashCommandGroup]:
    grouped_cmd_dict = {"General": {}}
    for cmd_name, cmd in cmds_dict.items():
        try:
            cmd.subcommands
        except AttributeError:
            grouped_cmd_dict["General"][cmd_name] = cmd
        else:
            if command_group_size(cmd.subcommands) > 1:
                friendly_name = cmd_name.capitalize().replace("_", " ")
                grouped_cmd_dict[friendly_name] = {cmd_name: cmd}
            else:
                grouped_cmd_dict["General"][cmd_name] = cmd

    return grouped_cmd_dict


def build_help_lines(
    cmds_dict: t.Dict[str, lb.SlashCommand | lb.SlashGroupMixin],
    parents: t.List[str] = [],
    include_hidden: bool = False,
) -> t.List[str]:
    help_single_page = []

    for cmd_name, cmd in cmds_dict.items():
        cmd: lb.SlashCommand | lb.SlashGroupMixin

        if cmd.hidden and not include_hidden:
            continue

        try:
            cmd_group_size = command_group_size(cmd.subcommands)
        except AttributeError:
            subcommand_helps = []
        else:
            subcommand_helps = build_help_lines(
                cmd.subcommands, parents + [cmd_name], include_hidden=include_hidden
            )

        # Only include command groups in the help if they have more than one subcommand
        if (subcommand_helps and cmd_group_size > 1) or not subcommand_helps:
            help_single_page.append(
                f"`/{' '.join(parents + [cmd_name])}` - {cmd.description}"
            )

        help_single_page.extend(subcommand_helps)

    return help_single_page


def lines_to_embeds(
    help_text: t.List[str], embed_subheading: str = ""
) -> t.List[h.Embed]:
    pages = [""]
    for help_line in help_text:
        if len(pages[-1]) + len(help_line) > 1800 or len(pages[-1].split("\n")) > 64:
            pages.append("")

        if len(help_line) > 2000:
            help_line = help_line[:2000]
            logging.warning(f"Help line too long, truncating: {help_line}")

        pages[-1] += "\n\n" + help_line

    embed_heading = "# Bot Help"
    if embed_subheading:
        embed_heading += f"\n### {embed_subheading}"
    embed_heading += "\n\n"

    # Convert pages to embeds
    pages = [
        h.Embed(description=embed_heading + page, colour=cfg.embed_default_color)
        for page in pages
    ]

    return pages


class HelpCommand(lb.DefaultHelpCommand):
    async def send_bot_help(self, ctx: lb.Context) -> None:
        bot: lb.BotApp = ctx.app
        include_hidden = ctx.author.id in await bot.fetch_owner_ids()

        # Notes:
        # lb.SlashCommand & lb.SlashCommandGroups have the following attributes:
        #  - name: str
        #  - description: str
        #  - hidden: bool
        #  - subcommands: t.MutableMapping[str, lb.SlashCommand | lb.SlashGroupMixin]
        #  - help_getter: t.Optional[t.Callable[[], str]]

        regrouped_cmds = regroup_commands(bot.slash_commands)

        pages = []
        buttons = []
        page_no = 0
        for cmd_name, cmd_dict in regrouped_cmds.items():
            help_text_lines = build_help_lines(cmd_dict, include_hidden=include_hidden)

            if not help_text_lines:
                continue

            embeds = lines_to_embeds(
                help_text_lines,
                embed_subheading=cmd_name + " commands",
            )

            for page_sub_no, embed in enumerate(embeds):
                pages.append(embed)
                label = cmd_name
                if page_sub_no > 0:
                    label += f" {to_roman(page_sub_no + 1)}"
                buttons.append(NumberedButton(page_number=page_no, label=label))
                page_no += 1

        if len(pages) > 1:
            view = nav.NavigatorView(
                pages=pages, buttons=buttons, timeout=cfg.navigator_timeout
            )
            await view.send(ctx.interaction)
        else:
            await ctx.respond(list(pages.values())[0])

    async def send_command_help(self, ctx: lb.Context, command: lb.Command) -> None:
        long_help = command.get_help(ctx)
        lines = [
            "## Command help",
            f"### {command.name.capitalize()}",
            f"{command.description}",
            "",
            f"Usage: `/{command.signature}`",
            "",
            long_help if long_help else "",
        ]
        await ctx.respond(
            h.Embed(description="\n".join(lines), color=cfg.embed_default_color)
        )

    async def send_group_help(
        self,
        context: lb.Context,
        group: lb.PrefixCommandGroup
        | lb.PrefixSubGroup
        | lb.SlashCommandGroup
        | lb.SlashSubGroup,
    ) -> None:
        long_help = group.get_help(context)

        lines = [
            "# Command group help",
            f"## {group.name.capitalize()}",
            f"{group.description}",
            "",
            f"Usage: `/{group.qualname} [subcommand]`",
        ]
        if long_help:
            lines.extend(
                [
                    "",
                    long_help if long_help else "",
                    "",
                ]
            )
        if group._subcommands:
            subcommands = await lb.filter_commands(group._subcommands.values(), context)
            lines.append("### Subcommands")
            for cmd in set(subcommands):
                lines.append(f"- `{cmd.name}` - {cmd.description}")

        await context.respond(
            h.Embed(description="\n".join(lines), colour=cfg.embed_default_color)
        )

    async def send_plugin_help(self, ctx: lb.Context, plugin: lb.Plugin) -> None:
        logging.warning(f"Plugin help command access attempted for plugin {plugin}")
        await ctx.respond("Not implemented")
