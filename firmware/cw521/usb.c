/*
  Copyright (c) 2014-2018 NewAE Technology Inc. All rights reserved.

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include <asf.h>
#include "conf_usb.h"
#include "stdio_serial.h"
#include "ui.h"
#include "genclk.h"
#include "usb.h"
#include "fpga_xmem.h"
#include <string.h>
#include <stdint.h>

#define FW_VER_MAJOR 1
#define FW_VER_MINOR 0
#define FW_VER_DEBUG 0

volatile bool g_captureinprogress = true;

static volatile bool main_b_vendor_enable = true;

static uint32_t state[4];
static uint32_t seed[4];

COMPILER_WORD_ALIGNED
static uint8_t main_buf_loopback[MAIN_LOOPBACK_SIZE];

void main_vendor_bulk_in_received(udd_ep_status_t status,
                                  iram_size_t nb_transfered, udd_ep_id_t ep);
void main_vendor_bulk_out_received(udd_ep_status_t status,
                                   iram_size_t nb_transfered, udd_ep_id_t ep);

static uint8_t done = 0;
void main_suspend_action(void)
{
     ui_powerdown();
}

void main_resume_action(void)
{
     ui_wakeup();
}

void main_sof_action(void)
{
     if (!main_b_vendor_enable)
          return;
     ui_process(udd_get_frame_number());
}

bool main_vendor_enable(void)
{
     LED_On(LED2_GPIO);
     main_b_vendor_enable = true;
     // Start data reception on OUT endpoints
#if UDI_VENDOR_EPS_SIZE_BULK_FS
     //main_vendor_bulk_in_received(UDD_EP_TRANSFER_OK, 0, 0);
     udi_vendor_bulk_out_run(
          main_buf_loopback,
          sizeof(main_buf_loopback),
          main_vendor_bulk_out_received);
#endif
     return true;
}

void main_vendor_disable(void)
{
     main_b_vendor_enable = false;
}

#define REQ_MEMREAD_BULK 0x10
#define REQ_MEMWRITE_BULK 0x11
#define REQ_MEMREAD_CTRL 0x12
#define REQ_MEMWRITE_CTRL 0x13
#define REQ_FW_VERSION 0x17
#define REQ_SAM3U_CFG 0x22
#define REQ_MEMWRITE_RNG 0x14
#define REQ_CHECKMEM_RNG 0x15
#define REQ_ECHO_SEED 0x16
#define REQ_MEMREAD_RNG_BULK 0x18

COMPILER_WORD_ALIGNED static uint8_t ctrlbuffer[64];
#define CTRLBUFFER_WORDPTR ((uint32_t *) ((void *)ctrlbuffer))

typedef enum {
     bep_emem=0,
     bep_fpgabitstream=10
} blockep_usage_t;

static blockep_usage_t blockendpoint_usage = bep_emem;

static uint8_t * ctrlmemread_buf;
static unsigned int ctrlmemread_size;
uint32_t sram_size = 4194304UL;
static int seeded = 0;

void ctrl_readmem_bulk(void);
void ctrl_readmem_ctrl(void);
void ctrl_writemem_bulk(void);
void ctrl_writemem_ctrl(void);
void ctrl_progfpga_bulk(void);

void ctrl_echo_seed(void);
void ctrl_testmem(void);

void ctrl_readmem_rng_bulk(void);
void ctrl_writemem_rng(void);

uint32_t xorshift128(void);
uint32_t xorshift32(void);
#undef XOR_32
#ifdef XOR_32
#define xorshift() xorshift32()
#else
#define xorshift() xorshift128()
#endif

//PSRAM is SMC memory
static uint8_t buffer[9000];
static uint16_t found_err[] = {0,0};
	
volatile static uint8_t rng_done = 0;
uint8_t testmem_sent_back = 1;
void ctrl_testmem(void)
{
     uint32_t buflen = *(CTRLBUFFER_WORDPTR);
     uint32_t address = *(CTRLBUFFER_WORDPTR + 1);
     if (address > (sram_size - buflen) )
          return;
     int i =0;
     if (buflen >= sizeof(buffer))
          return;
     LED_On(LED2_GPIO);
     if (!address) {
          for (i = 0; i < 4; i++) {
               state[i] = seed[i];
          }
          found_err[1] = 0;
          done = 0;
     }

     found_err[0] = 0;
     found_err[1]++;
     for (i = 0; i < buflen / 4; i++) {
          int j = 0;
          uint32_t rng_val = xorshift();
          for (j = 0; j < 4; j++) {
               buffer[i * 4 + j] = xram[i * 4 + j + address] ^ ((rng_val >> (8 * j)) & 0xFF);
               if (buffer[i * 4 + j]) {
                    found_err[0] = 1;
               }
          }
     }

     ctrlmemread_buf = (uint8_t *) found_err;
     ctrlmemread_size = 4;
}

void ctrl_readmem_bulk(void){
     uint32_t buflen = *(CTRLBUFFER_WORDPTR);
     uint32_t address = *(CTRLBUFFER_WORDPTR + 1);

     FPGA_setlock(fpga_blockin);

     LED_On(LED2_GPIO);

     /* Do memory read */
     udi_vendor_bulk_in_run(
          (uint8_t *) PSRAM_BASE_ADDRESS + address,
          buflen,
          main_vendor_bulk_in_received
          );
}

void ctrl_readmem_rng_bulk(void){
	uint32_t buflen = *(CTRLBUFFER_WORDPTR);
	//uint32_t address = *(CTRLBUFFER_WORDPTR + 1);
		
	//Oops? Can't do that with seeded version
	if (buflen >= sizeof(buffer))
	return;

	LED_On(LED2_GPIO);

	udi_vendor_bulk_in_run(
		buffer,
		buflen,
		main_vendor_bulk_in_received
	);
	return;
}

void ctrl_readmem_ctrl(void){
     uint32_t buflen = *(CTRLBUFFER_WORDPTR);
     uint32_t address = *(CTRLBUFFER_WORDPTR + 1);

     FPGA_setlock(fpga_ctrlmem);

     /* Do memory read */
     ctrlmemread_buf = (uint8_t *) PSRAM_BASE_ADDRESS + address;

     /* Set size to read */
     ctrlmemread_size = buflen;

     /* Start Transaction */
     LED_On(LED2_GPIO);
}


uint32_t xorshift128(void)
{
     uint32_t s, t = state[3];
     t ^= t << 11;
     t ^= t >> 8;
     state[3] = state[2];
     state[2] = state[1];
     s = state[0];
     state[1] = state[0];

     t ^= s;
     t ^= s >> 19;

     state[0] = t;
     return t;
}

uint32_t xorshift32(void)
{
     uint32_t x = *state;
     x ^= x << 13;
     x ^= x >> 17;
     x ^= x << 15;
     *state = x;
     return x;
}

void ctrl_echo_seed(void)
{
     ctrlmemread_buf = (uint8_t *)seed;
     ctrlmemread_size = 16;
}

void ctrl_writemem_rng(void)
{
     uint32_t buflen = *(CTRLBUFFER_WORDPTR);
     uint32_t address = *(CTRLBUFFER_WORDPTR + 1);
     int i = 0;
     LED_On(LED1_GPIO);
     if (!address) {
          for (i = 0; i < 4; i++) {
               state[i] = CTRLBUFFER_WORDPTR[i + 2];
               seed[i] = state[i];
          }
     }
     uint32_t num_rng = buflen / 4;
     for (i = 0; i < num_rng; i++) {
          uint32_t rng_val = xorshift();
          int j = 0;
          for (j = 0; j < 4; j++) {
               xram[i * 4 + j + address] = (rng_val >> (8 * j)) & 0xFF;
          }
     }
     seeded = 1;
}

void ctrl_writemem_ctrl(void){
     uint32_t buflen = *(CTRLBUFFER_WORDPTR);
     uint32_t address = *(CTRLBUFFER_WORDPTR + 1);

     uint8_t * ctrlbuf_payload = (uint8_t *)(CTRLBUFFER_WORDPTR + 2);

     //printf("Writing to %x, %d\n", address, buflen);

     FPGA_setlock(fpga_generic);

     /* Start Transaction */
     LED_On(LED1_GPIO);

     /* Do memory write */
     for(unsigned int i = 0; i < buflen; i++){
          xram[i+address] = ctrlbuf_payload[i];
     }

     FPGA_setlock(fpga_unlocked);
}

static uint32_t bulkread_address = 0;
static uint32_t bulkread_len = 0;

void ctrl_writemem_bulk(void){
     uint32_t buflen = *(CTRLBUFFER_WORDPTR);
     uint32_t address = *(CTRLBUFFER_WORDPTR + 1);

     FPGA_setlock(fpga_blockout);

     /* Set address */
     bulkread_address = address;
     bulkread_len = buflen;
     //FPGA_setaddr(address);

     /* Transaction done in generic callback */
     LED_On(LED1_GPIO);
}

static void ctrl_sam3ucfg_cb(void)
{
     switch(udd_g_ctrlreq.req.wValue & 0xFF)
     {
          /* Turn on slow clock */
     case 0x01:
          osc_enable(OSC_MAINCK_XTAL);
          osc_wait_ready(OSC_MAINCK_XTAL);
          pmc_switch_mck_to_mainck(CONFIG_SYSCLK_PRES);
          break;

          /* Turn off slow clock */
     case 0x02:
          pmc_switch_mck_to_pllack(CONFIG_SYSCLK_PRES);
          break;

          /* Jump to ROM-resident bootloader */
	case 0x03:	
		/* Clear ROM-mapping bit. */
		efc_perform_command(EFC0, EFC_FCMD_CGPB, 1);
		
		/* Disconnect USB (will kill connection) */
		udc_detach();
		
		/* With knowledge that I will rise again, I lay down my life. */
		while (RSTC->RSTC_SR & RSTC_SR_SRCMP);
		RSTC->RSTC_CR |= RSTC_CR_KEY(0xA5) | RSTC_CR_PERRST | RSTC_CR_PROCRST;
		while(1);
		break;
		
     default:
          break;
     }
}

bool main_setup_out_received(void)
{
     //Add buffer if used
     udd_g_ctrlreq.payload = ctrlbuffer;
     udd_g_ctrlreq.payload_size = min(udd_g_ctrlreq.req.wLength,	sizeof(ctrlbuffer));

     blockendpoint_usage = bep_emem;

     switch(udd_g_ctrlreq.req.bRequest){
          /* Memory Read */
     case REQ_MEMREAD_BULK:
          udd_g_ctrlreq.callback = ctrl_readmem_bulk;
          return true;
     case REQ_MEMREAD_CTRL:
          udd_g_ctrlreq.callback = ctrl_readmem_ctrl;
          return true;

          /* Memory Write */
     case REQ_MEMWRITE_BULK:
          udd_g_ctrlreq.callback = ctrl_writemem_bulk;
          return true;

     case REQ_MEMWRITE_CTRL:
          udd_g_ctrlreq.callback = ctrl_writemem_ctrl;
          return true;

          /* Memory Read for special seeded version */
     case REQ_MEMREAD_RNG_BULK:
          udd_g_ctrlreq.callback = ctrl_readmem_rng_bulk;
          return true;

          /* Misc hardware setup */
     case REQ_SAM3U_CFG:
          udd_g_ctrlreq.callback = ctrl_sam3ucfg_cb;
          return true;

     case REQ_MEMWRITE_RNG:
          /* udd_g_ctrlreq.callback = ctrl_writemem_rng; */
          ctrl_writemem_rng();
          /* while (!rng_done) */
          return true;
     case REQ_CHECKMEM_RNG:
          udd_g_ctrlreq.callback = ctrl_testmem;
          return true;

     default:
          return false;
     }
}


/*
  udd_g_ctrlreq.req.bRequest == 0


  && (udd_g_ctrlreq.req.bRequest == 0)
  && (0 != udd_g_ctrlreq.req.wLength)
*/

bool main_setup_in_received(void)
{
     /*
       udd_g_ctrlreq.payload = main_buf_loopback;
       udd_g_ctrlreq.payload_size =
       min( udd_g_ctrlreq.req.wLength,
       sizeof(main_buf_loopback) );
     */

     static uint8_t  respbuf[64];

     switch(udd_g_ctrlreq.req.bRequest){
     case REQ_CHECKMEM_RNG:
     case REQ_MEMREAD_CTRL:
          udd_g_ctrlreq.payload = ctrlmemread_buf;
          udd_g_ctrlreq.payload_size = ctrlmemread_size;
          ctrlmemread_size = 0;

          if (FPGA_lockstatus() == fpga_ctrlmem){
               FPGA_setlock(fpga_unlocked);
          }

          return true;
          break;

     case REQ_FW_VERSION:
          respbuf[0] = FW_VER_MAJOR;
          respbuf[1] = FW_VER_MINOR;
          respbuf[2] = FW_VER_DEBUG;
          udd_g_ctrlreq.payload = respbuf;
          udd_g_ctrlreq.payload_size = 3;
          return true;
          break;


     default:
          return false;
     }
     return false;
}

void main_vendor_bulk_in_received(udd_ep_status_t status,
                                  iram_size_t nb_transfered, udd_ep_id_t ep)
{
     UNUSED(nb_transfered);
     UNUSED(ep);
     if (UDD_EP_TRANSFER_OK != status) {
          return; // Transfer aborted/error
     }

     if (FPGA_lockstatus() == fpga_blockin){
          FPGA_setlock(fpga_unlocked);
     }
}

void main_vendor_bulk_out_received(udd_ep_status_t status,
                                   iram_size_t nb_transfered, udd_ep_id_t ep)
{
     UNUSED(ep);
     if (UDD_EP_TRANSFER_OK != status) {
          // Transfer aborted

          //restart
          udi_vendor_bulk_out_run(
               main_buf_loopback,
               sizeof(main_buf_loopback),
               main_vendor_bulk_out_received);

          return;
     }

     if (blockendpoint_usage == bep_emem){

          for(uint32_t i = 0; i < nb_transfered; i++){
               xram[i + bulkread_address] = main_buf_loopback[i];
          }

          if (FPGA_lockstatus() == fpga_blockout){
               FPGA_setlock(fpga_unlocked);
          }
     }
     //printf("BULKOUT: %d bytes\n", (int)nb_transfered);

     udi_vendor_bulk_out_run(
          main_buf_loopback,
          sizeof(main_buf_loopback),
          main_vendor_bulk_out_received);
}
