"""Prueba mínima: prender, rojo, esperar 3 s, apagar (comandos directos con bleak)."""
import asyncio
import sys
import time

from bleak import BleakClient

ADDRESS = sys.argv[1] if len(sys.argv) > 1 else "BE:30:18:00:61:BE"
WRITE_UUID = "0000ee02-0000-1000-8000-00805f9b34fb"

TURN_ON = bytes.fromhex("69 96 02 01 01")
TURN_OFF = bytes.fromhex("69 96 02 01 00")


def color(r, g, b):
    return bytes.fromhex("69 96 05 02") + bytes([r, g, b])


async def send(client, label, data):
    # response=True: la luz confirma la escritura, así un fallo se nota como excepción
    await client.write_gatt_char(WRITE_UUID, data, response=True)
    print(f"[{time.strftime('%H:%M:%S')}] {label:<8} -> {data.hex(' ')}")


async def main():
    print(f"Conectando a {ADDRESS}...")
    async with BleakClient(ADDRESS, timeout=20) as client:
        print("Conectado.\n")
        await send(client, "PRENDER", TURN_ON)
        await asyncio.sleep(1)
        await send(client, "ROJO", color(255, 0, 0))
        await asyncio.sleep(3)
        await send(client, "APAGAR", TURN_OFF)
    print("\nDesconectado. Prueba terminada.")


if __name__ == "__main__":
    asyncio.run(main())
