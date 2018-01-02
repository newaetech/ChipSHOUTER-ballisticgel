
import random
import numpy as np

import numpy as np
import matplotlib.mlab as mlab
import matplotlib.pyplot as plt

import srammap
import chipwhisperer.hardware.naeusb.naeusb as NAE

class CW521(object):

    sram_len = 4194304

    def con(self, usb_vid=0x2B3E, usb_pid=0xC305):

        self.usb = NAE.NAEUSB()
        self.usb.con(idProduct=[usb_pid])


    def write_pattern(self, pattern):
        """Download an arbitrary pattern to the SRAM"""

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


    def read_pattern(self, start_addr=0, len_to_read=None):
        """Read SRAM contents"""

        if len_to_read is None:
            len_to_read = self.sram_len

        if len_to_read < 0:
            len_to_read = self.sram_len + len_to_read
            
        if (len_to_read + start_addr) > self.sram_len:
            raise ValueError("len_to_read (%d) is too long"%len_to_read)

        din = self.usb.cmdReadMem(start_addr, len_to_read)

        return din

    def close(self):
        self.usb.close()

        
def do_test():

    cw521 = CW521()
    cw521.con()

   
    #Generate random test vector (so when re-run know if write was working)
    print "Generating test vector %d bytes"%cw521.sram_len
    data = np.random.randint(0, 256, cw521.sram_len)

    print "Writing..."
    cw521.write_pattern(data)

    raw_input("Hit Enter once Glitch inserted")

    print "Reading..."

    din = cw521.read_pattern()
    
    errorcnt = 0

    errorlist = []

    test_len = cw521.sram_len

    for i in range(0, test_len):
        if data[i] != din[i]:
            errorlist.append(bin(data[i] ^ din[i]).count('1'))
            errorcnt += 1
        else:
            errorlist.append(0)
            
    print "Errors: %d (of %d)"%(errorcnt, test_len)

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
    do_test()

#do_test()
