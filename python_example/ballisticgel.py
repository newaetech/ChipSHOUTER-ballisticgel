
import random
import numpy as np

import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt

import srammap
import chipwhisperer.hardware.naeusb.naeusb as NAE
import time

class CW521(object):

    REQ_CHECKMEM_RNG = 0x15
    REQ_MEMWRITE_RNG = 0x14

    sram_len = 4194304

    def con(self, usb_vid=0x2B3E, usb_pid=0xC305):

        self.usb = NAE.NAEUSB()
        self.usb.con(idProduct=[usb_pid])


    def write_pattern(self, pattern):
        """Download an arbitrary pattern to the entire SRAM"""

        if len(pattern) > self.sram_len:
            raise ValueError("Length of pattern (%d) too long"%(len(pattern)))

        #Break into 1024 chunks on write - required to avoid buffer overflow!
        totalsent = 0
        chunksize = 1000
        if len(pattern) < chunksize:
            self.usb.cmdWriteMem(0, data)
            totalsent += len(pattern)
        else:
            lastendaddr = 0
            for chunkstart in range(0, len(pattern), chunksize):
                lastendaddr = (chunkstart + chunksize)
                chunk = pattern[chunkstart:lastendaddr]
                self.usb.cmdWriteMem(chunkstart, chunk)
                totalsent += len(chunk)

            if totalsent != len(pattern):
                chunk = pattern[lastendaddr:]
                self.usb.cmdWriteMem(lastendaddr, chunk)

    def write_seed(self, seed, addr, length):
        """Write 'length' random data to 'addr', based on 'seed'"""
        if (len(seed) != 16):
            raise ValueError("Length of seed incorrect {}".format(len(seed)))
        pload = packuint32(length)
        pload.extend(packuint32(addr))
        pload.extend(seed)
        self.usb.sendCtrl(self.REQ_MEMWRITE_RNG, data=pload)


    def read_pattern(self, start_addr=0, len_to_read=None):
        """Read a block of data from SRAM."""

        if len_to_read is None:
            len_to_read = self.sram_len

        if len_to_read < 0:
            len_to_read = self.sram_len + len_to_read

        if (len_to_read + start_addr) > self.sram_len:
            raise ValueError("len_to_read (%d) is too long"%len_to_read)

        din = self.usb.cmdReadMem(start_addr, len_to_read)

        return din

    def read_pattern_rng(self, addr, size = 4096):
        """Read error pattern, assuming it was written using seed previously."""
        
        if size > 8192:
            raise ValueError("Read pattern too large")

        pload = packuint32(size)
        pload.extend(packuint32(addr))
        self.usb.sendCtrl(self.REQ_CHECKMEM_RNG, data=pload)
        data = self.usb.readCtrl(self.REQ_CHECKMEM_RNG, dlen = 4)
        reported_count = (data[3] << 8) | data[2]
        reported_count -= 1
        
        # Check if any errors reported - if not we return a null pattern array without needing to do
        # USB transfers at all
        if data[0] == 0:
            return [0] * size
        else:
            print "Error in block {} ({}) (addr = {}, size = {})".format(addr / size, reported_count, addr, size)
            return self.usb.cmdReadMem(addr, size)

    def close(self):
        self.usb.close()

def packuint32(data):
    """Converts a 32-bit integer into format expected by USB firmware"""

    return [data & 0xff, (data >> 8) & 0xff, (data >> 16) & 0xff, (data >> 24) & 0xff]

def get_xor_sram(sram_len):
    data = np.random.randint(0, 256, sram_len)
    print "Generating xor"
    for i in range(sram_len / 4):
        if (not (i % 10000)):
            print "Done {}".format(i)
        rng_val = xorshift128()
        for j in range(4):
            data[i * 4 + j] = (rng_val >> (8 * j)) & 0xFF
    return data

def do_seed_test():
    cw521 = CW521()
    cw521.con()
    state = []
    for i in range(0, 4):
        state.extend(packuint32(0xFAA2))

    print "Writing seed"
    block_size = 8192
    time1 = time.clock()

    # Have to do one extra?
    for i in range(cw521.sram_len / block_size + 1):
        cw521.write_seed(state, i * block_size, block_size)
    # cw521.write_pattern(data)
    time2 = time.clock()
    write_time = time2 - time1

    #Generate random test vector (so when re-run know if write was working)
    # print "Generating test vector %d bytes"%cw521.sram_len

    # time1 = time.clock()
    # data = get_xor_sram(cw521.sram_len)
    # time2 = time.clock()
    # pattern_time = time2 - time1


    raw_input("Hit Enter once Glitch inserted")

    print "Reading..."

    time1 = time.clock()
    errorlist = []
    for i in range(0, cw521.sram_len / block_size):
        errorlist.extend(cw521.read_pattern_rng(i * block_size, block_size))
    time2 = time.clock()
    read_time = time2 - time1

    test_len = cw521.sram_len
    time1 = time.clock()
    byte_errors = 0
    for i in range(0, len(errorlist)):
        if not errorlist[i] == 0:
            byte_errors += 1;

    time2 = time.clock()
    check_time = time2 - time1

    print "Byte errors: {}".format(byte_errors)
    print "Write: {}, Read: {}, Check: {}".format(write_time, read_time, check_time)

    sram = srammap.SRAMMapping()
    errdatax = []
    errdatay = []
    pone = False
    for i in range(0, 2**22, 2):
        err = errorlist[i] | errorlist[i + 1]

        if err > 0:
            locs = sram.get_bit_locations(i >> i)
            x = locs[0]
            ybitarray = locs[1]
            for bnum in range(0, 16):
                if err & (1<<bnum):
                    errdatax.append(x)
                    errdatay.append(ybitarray[bnum])

    plt.plot(errdatax, errdatay, '.r')
    plt.axis([0, 8192, 0, 4096])
    plt.show()

    with open("error_location.bin", "wb") as errfile:
        errfile.write(bytearray(errorlist))
    cw521.close()

def do_test():

    cw521 = CW521()
    cw521.con()

    #Generate random test vector (so when re-run know if write was working)
    print "Generating test vector %d bytes"%cw521.sram_len

    time1 = time.clock()
    data = np.random.randint(0, 256, cw521.sram_len)
    time2 = time.clock()
    pattern_time = time2 - time1

    print "Writing..."
    time1 = time.clock()
    cw521.write_pattern(data)
    time2 = time.clock()
    write_time = time2 - time1

    raw_input("Hit Enter once Glitch inserted")

    print "Reading..."

    time1 = time.clock()
    din = cw521.read_pattern()
    time2 = time.clock()
    read_time = time2 - time1

    errorcnt = 0

    errorlist = []
    set_errors = []
    reset_errors = []

    test_len = cw521.sram_len

    time1 = time.clock()
    for i in range(0, test_len):
        if data[i] != din[i]:
            diff = data[i] ^ din[i]
            errorlist.append(bin(diff).count('1'))
            set_errors.append(bin(diff & data[i]).count('1'))
            reset_errors.append(bin(diff & ~data[i]).count('1'))
            errorcnt += 1
        else:
            errorlist.append(0)
    time2 = time.clock()
    check_time = time2 - time1

    total_set_errors = sum(set_errors)
    total_reset_errors = sum(reset_errors)

    print "Byte errors: %d (of %d). Bit errors: %d set (0 --> 1), %d reset (1 --> 0)"%(errorcnt, test_len, total_set_errors, total_reset_errors)
    print " Timing: pattern: {}, Write: {}, Read: {}, Check: {}".format(pattern_time, write_time, read_time, check_time)

    if errorcnt > 0:
        sram = srammap.SRAMMapping()
        errdatax = []
        errdatay = []
        pone = False

        for i in range(0, 2**22, 2):
            err = errorlist[i] | errorlist[i + 1]
            if err > 0:
                #SAM3U to SRAM mapping has A1 mapped to A0 etc, so need to account
                #for addressing used here
                locs = sram.get_bit_locations(i >> 1)
                x = locs[0]
                ybitarray = locs[1]

                for bnum in range(0, 16):
                    if err & (1<<bnum):
                        errdatax.append(x)
                        errdatay.append(ybitarray[bnum])

        plt.plot(errdatax, errdatay, '.r')
        plt.axis([0, 8192, 0, 4096])
        plt.show()


    with open("error_location.bin", "wb") as errfile:
        errfile.write(bytearray(errorlist))

    cw521.close()

while True:
    state = []
    #do_seed_test()
    do_test()
