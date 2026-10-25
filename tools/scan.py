"""Escanea dispositivos BLE cercanos y resalta las luces MohuanLED (BJ_LED_M)."""
import asyncio

from bleak import BleakScanner

SCAN_SECONDS = 10
TARGET = "bj_led_m"


async def main():
    print(f"Escaneando {SCAN_SECONDS} s...\n")
    found = await BleakScanner.discover(timeout=SCAN_SECONDS, return_adv=True)

    rows = []
    for device, adv in found.values():
        name = adv.local_name or device.name or "(sin nombre)"
        rows.append((adv.rssi, name, device.address, adv.service_uuids))

    # RSSI más alto (menos negativo) = más cerca
    rows.sort(reverse=True)

    print(f"{'RSSI':>5}  {'MAC':<17}  Nombre")
    print("-" * 50)
    for rssi, name, address, _ in rows:
        mark = "  <-- LUZ" if TARGET in name.lower() else ""
        print(f"{rssi:>5}  {address:<17}  {name}{mark}")

    leds = [r for r in rows if TARGET in r[1].lower()]
    print(f"\nTotal: {len(rows)} dispositivos, {len(leds)} luz(ces) BJ_LED_M")
    for rssi, name, address, uuids in leds:
        print(f"  {name} {address} RSSI={rssi} servicios anunciados={uuids}")


if __name__ == "__main__":
    asyncio.run(main())
