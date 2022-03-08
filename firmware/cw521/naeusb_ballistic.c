#include "naeusb_ballistic.h"

static uint32_t state[4];
static uint32_t seed[4];

uint32_t sram_size = 4194304UL;
static int seeded = 0;

static blockep_usage_t blockendpoint_usage = bep_emem;

void main_vendor_bulk_in_received(udd_ep_status_t status,
                                  iram_size_t nb_transfered, udd_ep_id_t ep);
void main_vendor_bulk_out_received(udd_ep_status_t status,
                                   iram_size_t nb_transfered, udd_ep_id_t ep);

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
static uint8_t done = 0;

//PSRAM is SMC memory
static uint8_t buffer[9000];
static uint16_t found_err[] = {0,0};
static uint8_t * ctrlmemread_buf;
static unsigned int ctrlmemread_size;

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

void ctrl_readmem_bulk(void)
{
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

bool ballistic_setup_out_received(void)
{
     switch (udd_g_ctrlreq.req.bRequest) {
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
     return false;
}

bool ballistic_setup_in_received(void)
{
     switch (udd_g_ctrlreq.req.bRequest) {
          case REQ_CHECKMEM_RNG:
          case REQ_MEMREAD_CTRL:
               udd_g_ctrlreq.payload = ctrlmemread_buf;
               udd_g_ctrlreq.payload_size = ctrlmemread_size;
               ctrlmemread_size = 0;

               if (FPGA_lockstatus() == fpga_ctrlmem) {
                    FPGA_setlock(fpga_unlocked);
               }
               return true;
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
               xram[bulkread_address++] = main_buf_loopback[i];
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

void ballistic_register_handlers(void)
{
     naeusb_add_in_handler(ballistic_setup_in_received);
     naeusb_add_out_handler(ballistic_setup_out_received);
}