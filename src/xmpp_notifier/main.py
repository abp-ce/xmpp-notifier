import asyncio
from pathlib import Path
from typing import Annotated

import slixmpp
import typer
import yaml


class SendXMPPMsgBot(slixmpp.ClientXMPP):
    def __init__(self, jid, password, recipient, message):
        slixmpp.ClientXMPP.__init__(self, jid, password)

        self.recipient = recipient
        self.msg = message

        self.add_event_handler("session_start", self.start)

    async def start(self, _):
        self.send_presence()
        await self.get_roster()

        self.send_message(mto=self.recipient, mbody=self.msg, mtype="chat")

        await self.disconnect()


def send_message_to_xmpp(xmpp_bot, xmpp_pass, xmpp_recepient, message):

    async def send_message_to_xmpp_async():

        xmpp = SendXMPPMsgBot(xmpp_bot, xmpp_pass, xmpp_recepient, message)
        xmpp.register_plugin("xep_0030")
        xmpp.register_plugin("xep_0199")

        await xmpp.connect()

        await xmpp.disconnected

    asyncio.run(send_message_to_xmpp_async())


def load_config() -> dict:
    config_path = Path.home() / ".config" / "xmsg" / "config.yaml"
    if not config_path.exists():
        return {"senders": {}, "recipients": {}}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"senders": {}, "recipients": {}}
    except Exception:
        return {"senders": {}, "recipients": {}}


def create_app(config: dict) -> typer.Typer:
    app = typer.Typer()

    allowed_aliases = list(config.get("recipients", {}).keys())
    allowed_profiles = list(config.get("senders", {}).keys())

    def validate_recipient(value: str) -> str:
        if "@" in value or value in allowed_aliases:
            return value

        raise typer.BadParameter(
            f"'{value}' не является известным алиасом и не содержит '@'."
        )

    def validate_profile(value: str | None) -> str | None:
        if value is None:
            return value

        # Если передал, но такого имени нет в senders — Click выдаст красивую ошибку
        if value not in allowed_profiles:
            allowed = ", ".join(f"'{p}'" for p in allowed_profiles)
            raise typer.BadParameter(
                f"Профиль '{value}' не найден в config.yaml.\nДоступные профили: [{allowed}]"
            )
        return value

    base_help = "Алиас получателя из config.yaml или сырой JID со знаком '@'."

    choices_str = "|".join(allowed_aliases) if allowed_aliases else "ALIAS"
    custom_metavar = f"[{choices_str}|RAW_JID]"
    profiles_str = "|".join(allowed_profiles) if allowed_profiles else "ALIAS"
    profile_metavar = f"[{profiles_str}]"

    @app.command(name="send")
    def _(
        to: Annotated[
            str,
            typer.Argument(
                callback=validate_recipient,
                metavar=custom_metavar,
                help=base_help,
            ),
        ],
        text: Annotated[str, typer.Argument(help="Текст сообщения")],
        profile: Annotated[
            str | None,
            typer.Option(
                "--profile",
                "-p",
                callback=validate_profile,
                metavar=profile_metavar,
                help="Принудительный выбор бота",
            ),
        ] = None,
    ):
        senders = config.get("senders", {})
        recipients = config.get("recipients", {})
        recipient_data = recipients.get(to, {})

        xmpp_recepient = recipient_data.get("jid") or to

        if not profile:
            profile = recipient_data.get("sender_profile") or "default"

        xmpp_bot = senders[profile].get("bot_jid")
        xmpp_pass = senders[profile].get("bot_pass")

        message = text
        try:
            send_message_to_xmpp(xmpp_bot, xmpp_pass, xmpp_recepient, message)
            typer.secho("🚀 Отправлено!", fg=typer.colors.GREEN)
        except Exception as e:
            typer.secho(f"❌ Ошибка: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)

    return app


# --- 📝 ДЛЯ ГЕНЕРАЦИИ ДОКУМЕНТАЦИИ (Скрытый холостой инстанс) ---
# Генератор typer-cli увидит этот объект 'app' на уровне модуля
# _docs_config = {"senders": {"default": {}}, "recipients": {}}
# app = create_app(_docs_config)


def main():
    config = load_config()
    app = create_app(config)
    app()


if __name__ == "__main__":
    main()
