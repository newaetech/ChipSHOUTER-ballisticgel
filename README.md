# ChipSHOUTER® CW521 Ballistic Gel

The CW521 is an Electro-Magnetic Fault Injection (EMFI) target. It is specially designed to help you understand fault injection patterns for a given tip.

It uses a large SRAM chip as a target, which has a relatively simple layout. This lets you understand how much of a given chip you are corrupting.

## GIT Layout

The GIT repository contains the following:

1) PCB gerber files.
2) Firmware for the microcontroller.
3) Python library / PC application.

## PC Application

The PC application is a simple example of using the Python library. This application does the following (via the library)

1. Downloads a pattern to the SRAM chip.
2. Waits for fault injection.
3. Uploads SRAM chip contents & determines corrupt locations.
4. Graphs map of physical SRAM locations.

The SRAM pattern can be something besides the random pattern, but the random pattern ensures "odd" corruptions (such as shorting address lines etc) will easily be caught.

## Building Firmware

The firmware is built using Atmel Studio 7, but could also be built on Linux using an ARM toolchain.

## Legal

Ballistic Gel is part of the ChipSHOUTER project (which is itself related to the ChipWhisperer project). It is also known as the CW521 target board, as documented at https://wiki.newae.com .

Ballistic Gel is an open-source project, and is released with the GPL license. Assembled boards can be purchased from NewAE Technology Inc at https://store.newae.com .

ChipSHOUTER is a registered trademark of NewAE Technoloy Inc. Note you CANNOT sell boards using the ChipSHOUTER name without permission, and you cannot use NewAE Technology Inc's USB VID on your own products as the USB-IF license disallows sub-licensing in this manner. If you change the VID/PID, simply change the associated VID/PID in the .inf (driver) file as needed.
