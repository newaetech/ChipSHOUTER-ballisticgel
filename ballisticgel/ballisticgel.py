# Copyright (c) 2018-2019, NewAE Technology Inc
# All rights reserved.
#
# Authors: Colin O'Flynn, Alex Dewar
#
# This file is part of the ChipSHOUTER Ballistic Gel project.
#
#    This project is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This project is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this project.  If not, see <http://www.gnu.org/licenses/>.
#=============================================================================

import random

import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt
from .ChipWhispererSAM3Update import SAMFWLoader, get_at91_ports

from . import srammap
from . import naeusb as NAE
import time
from typing import Optional, Type, Union

def program_sam_firmware(serial_port : Optional[str]=None,
    hardware_type : Optional[str]=None, fw_path : Optional[str]=None):
    """Program firmware onto an erased chipwhisperer scope or target

    See https://chipwhisperer.readthedocs.io/en/latest/firmware.html for more information

    .. versionadded:: 5.6.1
        Improved programming interface
    """
    if (hardware_type, fw_path) == (None, None):
        raise ValueError("Must specify hardware_type or fw_path, see https://chipwhisperer.readthedocs.io/en/latest/firmware.html")

    if serial_port is None:
        at91_ports = get_at91_ports()
        if len(at91_ports) == 0:
            raise OSError("Could not find bootloader serial port, please see https://chipwhisperer.readthedocs.io/en/latest/firmware.html")
        if len(at91_ports) > 1:
            raise OSError("Found multiple bootloaders, please specify com port. See https://chipwhisperer.readthedocs.io/en/latest/firmware.html")

        serial_port = at91_ports[0]
        print("Found {}".format(serial_port))
    prog = SAMFWLoader(None)
    prog.program(serial_port, hardware_type=hardware_type, fw_path=fw_path)


def packuint32(data):
    """Converts a 32-bit integer into format expected by USB firmware"""

    return [data & 0xff, (data >> 8) & 0xff, (data >> 16) & 0xff, (data >> 24) & 0xff]

class CW521(object):
    """This class defines communications with CW521 Ballistic Gel Target"""

    REQ_CHECKMEM_RNG = 0x15
    REQ_MEMWRITE_RNG = 0x14
    REQ_MEMREAD_RNG_BULK = 0x18

    sram_len = 4194304
    _hw_type = "cw521"

    def _getNAEUSB(self):
        return self.usb

    def _getCWType(self):
        return "cw521"

    def con(self, usb_vid=0x2B3E, usb_pid=0xC521):
        """Connect to the Ballistic Gel, use default VID/PID"""

        self.usb = NAE.NAEUSB()
        self.usb.con(idProduct=[usb_pid])

    def upgrade_firmware(self):
        prog = SAMFWLoader(self)
        prog.auto_program()

    def write_pattern(self, pattern):
        """Download an arbitrary pattern to the entire SRAM"""

        if len(pattern) > self.sram_len:
            raise ValueError("Length of pattern (%d) too long"%(len(pattern)))

        #Break into 1024 chunks on write - required to avoid buffer overflow!
        totalsent = 0
        chunksize = 1024
        self.usb.cmdWriteMem(0, pattern)

    def write_seed(self, seed, addr, length):
        """Write 'length' random data to 'addr', based on 'seed', done on-board
        the CW521 so faster than downloading a specific pattern.
        """
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
            #Uncomment this to get details on-the-fly
            #print "Error in block {} ({}) (addr = {}, size = {})".format(addr / size, reported_count, addr, size)
            cmd = self.REQ_MEMREAD_RNG_BULK
            pload = packuint32(size)
            pload.extend(packuint32(addr))
            self.usb.sendCtrl(cmd, data=pload)
            return self.usb.usbdev().read(self.usb.rep, size, timeout=self.usb._timeout)

    def close(self):
        self.usb.close()


    def get_xor_sram(self, sram_len):
        data = np.random.randint(0, 256, sram_len)
        print("Generating xor")
        for i in range(sram_len / 4):
            if (not (i % 10000)):
                print("Done {}".format(i))
            rng_val = xorshift128()
            for j in range(4):
                data[i * 4 + j] = (rng_val >> (8 * j)) & 0xFF
        return data
               
    def seed_test_setup(self, seed=0xFAA2):
        """Setup the SRAM using a seed, target pattern generation is done on-device.
        After a fault is inserted, call seed_test_compare() to find fault numbers and
        locations."""
    
        state = []
        for i in range(0, 4):
            state.extend(packuint32(seed))
            
        self.block_size = 8192
        #time1 = time.clock()

        # Have to do one extra?
        for i in range(int(self.sram_len / self.block_size) + 1):
            self.write_seed(state, i * self.block_size, self.block_size)
        # self.write_pattern(data)
        #time2 = time.clock()
        #write_time = time2 - time1

        #Generate random test vector (so when re-run know if write was working)
        # print "Generating test vector %d bytes"%self.sram_len

        # time1 = time.clock()
        # data = get_xor_sram(self.sram_len)
        # time2 = time.clock()
        # pattern_time = time2 - time1
        
        
    def seed_test_compare(self):
        """Test the SRAM for faults, assuming it was previously setup with seed_test_setup()"""

        #time1 = time.clock()
        errorlist = []
        for i in range(0, int(self.sram_len / self.block_size)):
            errorlist.extend(self.read_pattern_rng(i * self.block_size, self.block_size))
        #time2 = time.clock()
        #read_time = time2 - time1

        test_len = self.sram_len
        #time1 = time.clock()
        byte_errors = 0
        for i in range(0, len(errorlist)):
            if not errorlist[i] == 0:
                byte_errors += 1

        #time2 = time.clock()
        #check_time = time2 - time1

        print("Byte errors: {}".format(byte_errors))
        #print "Write: {}, Read: {}, Check: {}".format(write_time, read_time, check_time)

        #print "Getting actual glitch locations in SRAM"
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

        return {'errorlist':np.array(errorlist, dtype=np.uint8), 'errdatax':np.array(errdatax, dtype=np.uint8), 
                'errdatay':np.array(errdatay, dtype=np.uint8)}

    def raw_test_setup(self):
        """Download a raw pattern to the SRAM, slower than the seed method but
        allows arbitrary patterns. After inserting a fault test the pattern with
        raw_test_compare()"""

        #Generate random test vector (so when re-run know if write was working)
        #print "Generating test vector %d bytes"%self.sram_len

        #time1 = time.clock()
        self.data = np.random.randint(0, 256, self.sram_len, dtype=np.uint8)
        #time2 = time.clock()
        #pattern_time = time2 - time1

        #print "Writing..."
        #time1 = time.clock()
        self.write_pattern(self.data)
        #time2 = time.clock()
        #write_time = time2 - time1

        return
        
    def raw_test_compare(self):
        """Check the SRAM for faults based on a raw pattern previously downloaded
        with raw_test_setup()"""

        #time1 = time.clock()
        din = self.read_pattern()
        din = np.array(din, dtype=np.uint8)
        #time2 = time.clock()
        #read_time = time2 - time1

        errorcnt = 0

        errorlist = []
        set_errors = []
        reset_errors = []

        test_len = self.sram_len

        #time1 = time.clock()
        diff_list = self.data ^ din

        def np_hamming(arr):
            hw_arr = np.zeros(np.shape(arr), dtype=np.uint8)
            for i in range(8):
                hw_arr += (arr & (1 << i)) >> i
            return hw_arr

        errorlist = np_hamming(diff_list)
        set_errors = np_hamming(diff_list & self.data)
        reset_errors = np_hamming(diff_list & ~self.data)
            
        # for i in range(0, test_len):
        #     if self.data[i] != din[i]:

        #         diff = self.data[i] ^ din[i]
        #         errorlist.append(bin(diff).count('1'))
        #         set_errors.append(bin(diff & self.data[i]).count('1'))
        #         reset_errors.append(bin(diff & ~self.data[i]).count('1'))
        #         if bin(diff & ~self.data[i]).count('1') > 8:
        #             print("BULLSHIT DETECTED")
        #         errorcnt += 1
        #     else:
        #         errorlist.append(0)
        #time2 = time.clock()
        #check_time = time2 - time1

        total_set_errors = np.sum(set_errors, dtype=np.uint32)
        total_reset_errors = np.sum(reset_errors, dtype=np.uint32)

        print("Byte errors: %d (of %d). Bit errors: %d set (0 --> 1), %d reset (1 --> 0)"%(errorcnt, test_len, total_set_errors, total_reset_errors))
        #print " Timing: pattern: {}, Write: {}, Read: {}, Check: {}".format(pattern_time, write_time, read_time, check_time)

        errdatax = []
        errdatay = []
        if errorcnt > 0:
            sram = srammap.SRAMMapping()
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


        return {'errorlist':errorlist, 'errdatax':errdatax, 'errdatay':errdatay, 'set_errors':set_errors, 'reset_errors':reset_errors}

if __name__ == "__main__":

    print(" CW521 Ballistic Gel Example Script ")
    print("  by NewAE Technology Inc")
    print(" This script will continue until you exit with Ctrl-C")
    
    cw521 = CW521()
    cw521.con()
    
    doplot = False
    savefile = None
    #savefile = 'error_locations.bin' 
    
    #Raw method is slower but more flexible
    use_raw_method = False

    print("Settings: ")
    print("  Using slow (raw) mode  : " + str(use_raw_method))
    print("  Showing plot of results: " + str(doplot))
    print("  Results filename       : " + str(savefile))

    print("Starting main loop now: \n")
    
    while True:
        try:        
            if use_raw_method:
                print("LOOP START: Writing data to SRAM...")
                cw521.raw_test_setup()
                input(" Hit enter when glitch inserted")
                print(" Reading SRAM data...")
                results = cw521.raw_test_compare()
            else:
                print("LOOP START: Writing data to SRAM...")
                cw521.seed_test_setup()
                input(" Hit enter when glitch inserted")
                print(" Reading SRAM data...")
                results = cw521.seed_test_compare()
            
            errdatay = results['errdatay']
            errdatax = results['errdatax']
            errorlist = results['errorlist']
            
            if doplot:
                plt.plot(errdatax, errdatay, '.r')
                plt.axis([0, 8192, 0, 4096])
                plt.show()

            if savefile:
                with open(savefile, "wb") as errfile:
                    errfile.write(bytearray(errorlist))

            print("")
        
        except:
            cw521.close()
            raise



