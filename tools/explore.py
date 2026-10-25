"""Se conecta a la luz y lista sus servicios GATT y características."""
import asyncio
import sys

from bleak import BleakClient

ADDRESS = sys.argv[1] if len(sys.argv) > 1 else "BE:30:18:00:61:BE"


async def main():
    print(f"Conectando a {ADDRESS}...")
    async with BleakClient(ADDRESS, timeout=20) as client:
        print(f"Conectado: {client.is_connected}\n")

        for service in client.services:
            print(f"[Servicio] {service.uuid}  ({service.description})")
            for char in service.characteristics:
                props = ",".join(char.properties)
                print(f"   [Car.] {char.uuid}  handle={char.handle}  props=[{props}]  ({char.description})")

                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char)
                        print(f"          valor = {value.hex(' ')}  {value!r}")
                    except Exception as e:
                        print(f"          (no se pudo leer: {e})")

                for desc in char.descriptors:
                    print(f"          [Desc] {desc.uuid}  ({desc.description})")
            print()

        writable = [
            c for s in client.services for c in s.characteristics
            if {"write", "write-without-response"} & set(c.properties)
        ]
        print("Características escribibles:")
        for c in writable:
            print(f"   {c.uuid}  props={c.properties}")


if __name__ == "__main__":
    asyncio.run(main())
