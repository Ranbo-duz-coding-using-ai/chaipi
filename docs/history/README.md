# Design history

These are ChAIpi's earlier design docs, kept as a record. **They're superseded.** The current hardware is in [../12-revision-3.md](../12-revision-3.md), the wiring in [../03-wiring.md](../03-wiring.md), and the software in [../13-device-software.md](../13-device-software.md).

| Doc | From | What changed since |
|---|---|---|
| [01 — Hardware](01-hardware.md), [02 — Power](02-power.md) | Revision 1 | 1.3" OLED HAT replaced by a 2.8" colour TFT; new power chain |
| [04 — Controls and UI](04-controls-and-ui.md) | Revision 1 | Move entry by on-screen board and joystick instead of piece → file → rank |
| [05 — Engine](05-engine.md) | Revision 1 | Still mostly true. Elo and think-time details are now in doc 13 |
| [06 — Voice](06-voice.md) | Revision 1 | Voice input was dropped |
| [07 — Software](07-software.md), [08 — OS setup](08-os-setup.md) | Revision 1 | Replaced by the one-OS-two-hosts design and the custom image |
| [09 — Roadmap](09-roadmap.md), [10 — Enclosure](10-enclosure.md) | Revision 1 | The bring-up plan is now in doc 13 |
| [11 — Revision 2](11-revision-2.md) | Revision 2 | Its GPIO plan and power numbers were replaced in revision 3 |

The Python code in [legacy/phase0-prototype](../../legacy/phase0-prototype) is the prototype from this period (OLED + voice). It isn't used on the device.
