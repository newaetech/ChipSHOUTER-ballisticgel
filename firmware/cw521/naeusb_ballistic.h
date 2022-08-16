#pragma once
#include "naeusb/naeusb.h"
#include "naeusb/usb_xmem.h"

#define REQ_MEMWRITE_RNG 0x14
#define REQ_CHECKMEM_RNG 0x15
#define REQ_ECHO_SEED 0x16
#define REQ_MEMREAD_RNG_BULK 0x18
#define REQ_MEMREAD_BULK 0x10
#define REQ_MEMWRITE_BULK 0x11
#define REQ_MEMREAD_CTRL 0x12
#define REQ_MEMWRITE_CTRL 0x13

#define REQ_FPGA_RESET 0x25

typedef enum {
    bep_emem=0,
    bep_fpgabitstream=10
} blockep_usage_t;

void ballistic_register_handlers(void);