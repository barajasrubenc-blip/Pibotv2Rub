#inventario.py
import asyncio
from datetime import datetime, timedelta, timezone
import os
import random

from telegram import (
    ChatPermissions,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto
)
from telegram.error import TelegramError
from telegram.ext import ContextTypes
from src.database.database import (
    get_items,
    get_campo_item,
    get_id_item,
    get_campo_usuario,
    insert_user,
    normalizar_nombre,
    get_cantidad_item_inventario,
    update_cantidad,
    delete_item_user
    )
from src.config import BOT_USERNAME
from handlers.general import get_receptor
from handlers.tienda import mostrar_item

_silencios_temporales = {}


async def _restaurar_permisos_despues_de_silencio(
    application,
    chat_id: int,
    user_id: int,
    permissions: ChatPermissions,
) -> None:
    task = asyncio.current_task()
    try:
        await asyncio.sleep(10)
        await application.bot.restrict_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            permissions=permissions,
        )
    except TelegramError as exc:
        print(f"[WARNING] No se pudieron restaurar los permisos del usuario {user_id}: {exc}")
    finally:
        if _silencios_temporales.get((chat_id, user_id)) is task:
            _silencios_temporales.pop((chat_id, user_id), None)

def obtener_gif_aleatorio(nombre_producto):
    nombre_carpeta = nombre_producto.lower()

    # Carpeta relativa desde inventario.py
    ruta_carpeta = os.path.join(os.path.dirname(__file__), "..", "gifs_items", nombre_carpeta)

    # Normalizamos la ruta
    ruta_carpeta = os.path.abspath(ruta_carpeta)

    # Comprobamos que existe
    if not os.path.isdir(ruta_carpeta):
        print(f"No existe la carpeta: {ruta_carpeta}")
        return None, None

    # Listamos solo GIFs
    archivos = [f for f in os.listdir(ruta_carpeta) if f.endswith(".gif")]

    if not archivos:
        print(f"No hay GIFs en {ruta_carpeta}")
        return None, None

    # Elegimos uno al azar

    gif_seleccionado = random.choice(archivos)
    gif_path = os.path.join(ruta_carpeta, gif_seleccionado)

    # Caption basado en la descripción

    return gif_path

def main_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Menú principal", callback_data="volver_menu")]
    ])

def abrir_privado_button():
    bot_user = BOT_USERNAME or "PiBotBotBotBotBot"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💬 Abrir inventario en privado", url=f"https://t.me/{bot_user}?start=inventario")]
    ])

async def inventario(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    if update.effective_chat.type != "private":
        await update.message.reply_text(
            "🛑 El inventario solo está disponible en el chat privado.\n\n"
            "Haz clic aquí para abrirlo:",
            reply_markup=abrir_privado_button()
        )
        return
    
    user_id = update.effective_user.id

    # --- detectar si viene de callback ---
    query = update.callback_query
    if query:
        await query.answer()
        chat_id = query.message.chat_id
        message = query.message
    else:
        chat_id = update.effective_chat.id
        message = None

    # --- obtener items ---
    items = get_items(user_id)

    if not items:
        text = "📦 *Tu inventario está vacío*\nNo tienes ningún ítem todavía."
        if message:
            await message.edit_text(
                text,
                parse_mode="Markdown",
                reply_markup=main_menu_markup()
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=main_menu_markup()
            )
        return

    # --- paginación ---
    total_paginas = len(items)
    page = max(1, min(page, total_paginas))

    item = items[page - 1]

    id_item = item["id_item"]
    nombre = item["nombre"]
    precio = item["precio"]
    cantidad = item["cantidad"]
    img = item["imagen"]

    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ruta_imagen = os.path.join(BASE_DIR, img)

    caption = (
        f"📦 *INVENTARIO*\n\n"
        f"🧩 *{nombre}*\n"
        f"💰 Precio: {precio}\n"
        f"📦 Cantidad: {cantidad}\n\n"
        f"📄 Página {page}/{total_paginas}"
    )

    botones = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Ver", callback_data=f"ver_item_{id_item}")],
        [
            InlineKeyboardButton("⬅️", callback_data=f"inv_prev_{page}") if page > 1 else InlineKeyboardButton("❌", callback_data="none"),
            InlineKeyboardButton("➡️", callback_data=f"inv_next_{page}") if page < total_paginas else InlineKeyboardButton("❌", callback_data="none")
        ],
        [InlineKeyboardButton("⬅️ Volver al menú", callback_data="volver_menu")]
    ])

    # --- si NO viene de callback (primer mensaje) ---
    if not message:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open(ruta_imagen, "rb"),
            caption=caption,
            parse_mode="Markdown",
            reply_markup=botones
        )
        return

    # --- si VIENE del callback (next/prev) ---
    try:
        await message.edit_media(
            media=InputMediaPhoto(
                media=open(ruta_imagen, "rb"),
                caption=caption,
                parse_mode="Markdown"
            ),
            reply_markup=botones
        )
    except Exception:
        await context.bot.send_photo(
            chat_id=chat_id,
            photo=open(ruta_imagen, "rb"),
            caption=caption,
            parse_mode="Markdown",
            reply_markup=botones
        )

async def inventario_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data

    if data.startswith("inv_prev_"):
        actual = int(data.replace("inv_prev_", ""))
        await inventario(update, context, page=actual - 1)

    elif data.startswith("inv_next_"):
        actual = int(data.replace("inv_next_", ""))
        await inventario(update, context, page=actual + 1)

    elif data.startswith("ver_item_"):
        id_item = int(data.replace("ver_item_", ""))
        descripcion = get_campo_item(id_item, "descripcion")
        await mostrar_item(id_item, descripcion, update, context)

async def usar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat

    # 1. Crear usuario si no existe
    if get_campo_usuario(user.id, "id_user") is None:
        insert_user(user.id, 0, user.username,
                    normalizar_nombre(user.first_name, user.last_name))

    args = context.args

    # -------------------------------------
    # 2. Si no hay args y no hay reply → error
    # -------------------------------------
    if len(args) == 0 and not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ Debes escribir el nombre del ítem.\nEjemplo: `/usar latigo @usuario`",
            parse_mode="Markdown"
        )
        return

    # -------------------------------------
    # 3. Detectar la posición del @usuario
    # -------------------------------------
    pos_arroba = None
    for i, arg in enumerate(args):
        if arg.startswith("@"):
            pos_arroba = i
            break

    # Si NO viene en el comando pero sí es respuesta → receptor vía reply
    if pos_arroba is None and update.message.reply_to_message:
        receptor = await get_receptor(update, context, -1)

        # El nombre del ítem son todos los args
        nombre_item = " ".join(args).lower()
    else:
        # Si no hay receptor detectado → error
        if pos_arroba is None:
            await update.message.reply_text(
                "⚠️ Debes mencionar un usuario o responder un mensaje.",
                parse_mode="Markdown"
            )
            return

        # Pedimos el receptor indicando su posición exacta
        receptor = await get_receptor(update, context, pos_arroba + 1)

        if receptor is False or receptor is None:
            return

        # El nombre del ítem está antes del @usuario
        nombre_item = " ".join(args[:pos_arroba]).lower()

    # -------------------------------------
    # 4. Validar item
    # -------------------------------------
    item_id = get_id_item(nombre_item)

    if item_id is None:
        await update.message.reply_text(
            f"❌ El ítem *{nombre_item}* no existe.",
            parse_mode="Markdown"
        )
        return

    # -------------------------------------
    # 5. Validar cantidad
    # -------------------------------------
    cantidad = get_cantidad_item_inventario(user.id, item_id)
    if cantidad <= 0:
        nombre_real = get_campo_item(item_id, "nombre")
        await update.message.reply_text(
            f"❌ No tienes *{nombre_real}* en tu inventario.",
            parse_mode="Markdown"
        )
        return

    nombre_real = get_campo_item(item_id, "nombre")
    if nombre_real and nombre_real.casefold() == "bola mordaza":
        if chat.type != "supergroup":
            await update.message.reply_text(
                "❌ La bola mordaza solo puede usarse en un supergrupo; no se consumió."
            )
            return

        try:
            miembro = await context.bot.get_chat_member(chat.id, receptor.id)
            print(
                "[DEBUG] Bola mordaza get_chat_member: "
                f"status={miembro.status}, "
                f"is_member={getattr(miembro, 'is_member', None)}"
            )
            if miembro.status in ("administrator", "creator"):
                await update.message.reply_text(
                    "❌ No se puede silenciar a un administrador; no se consumió la bola mordaza."
                )
                return
            if miembro.status != "member":
                await update.message.reply_text(
                    "❌ El usuario no es un miembro silenciable de este grupo; no se consumió la bola mordaza."
                )
                return

            info_chat = await context.bot.get_chat(chat.id)
            permisos_previos = info_chat.permissions
            if permisos_previos is None:
                await update.message.reply_text(
                    "❌ No pude obtener los permisos del grupo; no se consumió la bola mordaza."
                )
                return

            await context.bot.restrict_chat_member(
                chat_id=chat.id,
                user_id=receptor.id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=datetime.now(timezone.utc) + timedelta(seconds=30),
            )
        except TelegramError as exc:
            print(f"[WARNING] No se pudo silenciar al usuario {receptor.id}: {exc}")
            await update.message.reply_text(
                "❌ No pude silenciar al usuario. Verifica que el bot tenga permisos de administrador; "
                "no se consumió la bola mordaza."
            )
            return

        clave_silencio = (chat.id, receptor.id)
        tarea_anterior = _silencios_temporales.get(clave_silencio)
        if tarea_anterior:
            tarea_anterior.cancel()
        _silencios_temporales[clave_silencio] = context.application.create_task(
            _restaurar_permisos_despues_de_silencio(
                context.application,
                chat.id,
                receptor.id,
                permisos_previos,
            ),
            update=update,
        )

    # -------------------------------------
    # 6. Restar item
    # -------------------------------------
    nueva_cantidad = cantidad - 1
    if nueva_cantidad > 0:
        update_cantidad(user.id, item_id, nueva_cantidad)
    else:
        delete_item_user(user.id, item_id)

    # -------------------------------------
    # 7. Obtener mensaje y gif random
    # -------------------------------------
    
    nombre_carpeta = nombre_item.lower()

    # Carpeta relativa desde inventario.py
    ruta_carpeta = os.path.join(os.path.dirname(__file__), "..", "gifs_items", nombre_carpeta)

    # Normalizamos la ruta
    ruta_carpeta = os.path.abspath(ruta_carpeta)

    # Comprobamos que existe
    if not os.path.isdir(ruta_carpeta):
        print(f"No existe la carpeta: {ruta_carpeta}")
        return None, None

    # Listamos solo GIFs
    archivos = [f for f in os.listdir(ruta_carpeta) if f.endswith(".gif")]

    if not archivos:
        print(f"No hay GIFs en {ruta_carpeta}")
        return None, None

    # Elegimos uno al azar

    gif_seleccionado = random.choice(archivos)
    
    gif_path = os.path.join(ruta_carpeta, gif_seleccionado)
    
    caption = get_campo_item(item_id, "mensaje")

    sender_username = user.username or normalizar_nombre(user.first_name, user.last_name)
    receptor_username = receptor.username or get_campo_usuario(receptor.id, "nombre")

    caption_final = caption.format(
        sender_username=sender_username,
        receptor_username=receptor_username
    )

    # -------------------------------------
    # 8. Enviar animación
    # -------------------------------------
    await context.bot.send_animation(
        chat_id=update.effective_chat.id,
        message_thread_id=update.message.message_thread_id,
        animation=open(gif_path, "rb"),
        caption=caption_final
    )