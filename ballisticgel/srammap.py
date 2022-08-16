#
# This file is Copyright (C) NewAE Technology Inc., 2017-2019. All Rights Reserved.
#
# Used to decode error/addressing information on the Ballistic Gel board target,
# the AS6C3216 SRAM chip. This was based on information for the AS6C3216, NOT the
# AS6C3216A used on the board. They seem to differ based on fault mapping, so work
# to improve this is ongoing...
#
# This file is part of Ballistic Gel
#
#    Ballistic Gel is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Ballistic Gel is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Foobar.  If not, see <http://www.gnu.org/licenses/>.
#

#
# A very very special thanks to Alliance Memory for providing detailed technical
# information that has made this mapping possible.
#

class SRAMMapping(object):
    """Provides mapping of AS6C3216A address to physical layout"""

    def address_to_xdecoder(self, address):
        """Given an address, provide xdecoder information (for AS6C3216A)"""
        #A7   = X12
        #A5   = X11
        #A2   = X10
        #A1   = X9
        #A0   = X8
        #A19  = X7
        #A17  = X6
        #A18  = X5
        #A6   = X4
        #A8   = X3
        #A9   = X2
        #A10  = X1
        #A16  = X0

        x = (((address >> 7)  & 0x01) << 12)  | \
            (((address >> 5)  & 0x01) << 11)  | \
            (((address >> 2)  & 0x01) << 10)  | \
            (((address >> 1)  & 0x01) << 9)   | \
            (((address >> 0)  & 0x01) << 8)   | \
            (((address >> 19) & 0x01) << 7)   | \
            (((address >> 17) & 0x01) << 6)   | \
            (((address >> 18) & 0x01) << 5)   | \
            (((address >> 6)  & 0x01) << 4)   | \
            (((address >> 8)  & 0x01) << 3)   | \
            (((address >> 9)  & 0x01) << 2)   | \
            (((address >> 10) & 0x01) << 1)   | \
            (((address >> 16) & 0x01) << 0)

        return x


    def address_to_xdecoder_AS6C3216(self, address):
        """Given an address, provide xdecoder information (for AS6C3216 - old version of SRAM array)"""
        x = (((address >> 20) & 0x01) << 12)  | \
            (((address >> 0)  & 0x01) << 11)  | \
            (((address >> 1)  & 0x01) << 10)  | \
            (((address >> 2)  & 0x01) << 9)   | \
            (((address >> 3)  & 0x01) << 8)   | \
            (((address >> 4)  & 0x01) << 7)   | \
            (((address >> 5)  & 0x01) << 6)   | \
            (((address >> 6)  & 0x01) << 5)   | \
            (((address >> 7)  & 0x01) << 4)   | \
            (((address >> 17) & 0x01) << 3)   | \
            (((address >> 18) & 0x01) << 2)   | \
            (((address >> 19) & 0x01) << 1)   | \
            (((address >> 8)  & 0x01) << 0)

        return x

    def address_to_ydecoder(self, address):
        """Given an address, provide ydecoder information (for AS6C3216A)"""
        #A20  = Y7
        #A4   = Y6
        #A3   = Y5
        #A15  = Y4
        #A14  = Y3
        #A13  = Y2
        #A12  = Y1
        #A11  = Y0

        y = (((address >> 20) & 0x01) << 7)  | \
            (((address >> 4)  & 0x01) << 6)  | \
            (((address >> 3)  & 0x01) << 5)  | \
            (((address >> 15) & 0x01) << 4)  | \
            (((address >> 14) & 0x01) << 3)  | \
            (((address >> 13) & 0x01) << 2)  | \
            (((address >> 12) & 0x01) << 1)  | \
            (((address >> 11) & 0x01) << 0)

        return y
   
    def address_to_ydecoder_AS6C3216(self, address):
        """Given an address, provide ydecoder information (for AS6C3216 - old version of chip)"""
        y = (((address >> 9)  & 0x01) << 7)  | \
            (((address >> 10) & 0x01) << 6)  | \
            (((address >> 11) & 0x01) << 5)  | \
            (((address >> 12) & 0x01) << 4)  | \
            (((address >> 13) & 0x01) << 3)  | \
            (((address >> 14) & 0x01) << 2)  | \
            (((address >> 15) & 0x01) << 1)  | \
            (((address >> 16) & 0x01) << 0)

        return y
   
   
    def xdecoder_to_wordline(self, x):
        """Go from x decoder to word line number"""

        #Bank defined by X12X11X10
        bank = (x >> 10) & 0x07

        #1024 wordlines in bank (wordlines run vertical)
        wline = x & 0x3FF

        #Odd banks are flipped as well, so count wordlines "backwards"
        if bank & 0x01:
            wline = 1024-wline

        #Index over number of banks
        wline = (bank * 1024) + wline

        #Return word line (basically X position on chip)
        return wline

    def ydecoder_to_bitlocations(self, y):
        """Go from y decoder to section, each section contains 512 bits"""

        #Section defined from Y7Y6Y5
        section = (y >> 5) & 0x07

        #Within section, each of Q0...Q15 in
        bitline_start = y & 0x1F

        #Each of Q0..Q15
        bitline_location = [bitline_start + (i*32) for i in range(0, 16)]

        #Odd sections will be flipped in Y
        #TODO: This is slightly different than expected, but visually
        #      makes more sense.
        if section & 0x01 == 0:
            bitline_location = [512 - bitline_location[i] for i in range(0, 16)]

        #Add segment offset
        bitline_location = [(section * 512) + bitline_location[i] for i in range(0, 16)]

        return bitline_location


    def get_bit_locations(self, address):
        """Go from address to x/y location. The y location is returned as a vector for each of 16 bits"""

        x = self.address_to_xdecoder(address)
        y = self.address_to_ydecoder(address)

        x = self.xdecoder_to_wordline(x)
        ybits = self.ydecoder_to_bitlocations(y)

        return (x, ybits)

    def errorbitlist_to_xyplot(self, errorlist, ax):
        """Convert SAM3U error bit location vector to graph"""

        errdatax = []
        errdatay = []

        for i in range(0, 2**22, 2):
            err = errorlist[i] | errorlist[i + 1]
            if err > 0:
                #SAM3U to SRAM mapping has A1 mapped to A0 etc, so need to account
                #for addressing used here
                locs = self.get_bit_locations(i >> 1)
                x = locs[0]
                ybitarray = locs[1]

                for bnum in range(0, 16):
                    if err & (1<<bnum):
                        errdatax.append(x)
                        errdatay.append(ybitarray[bnum])

        ax.plot(errdatax, errdatay, '.r')
        ax.axis([0, 8192, 0, 4096])
        ax.set_xticks(range(0, 8193, 1024))
        ax.set_yticks(range(0, 4097, 512))
        ax.set_ylim(ax.get_ylim()[::-1])
        ax.grid(True)

def test():
    with open("error_location.bin", "rb") as errfile:
        data = bytearray(errfile.read())

    sram = SRAMMapping()

    import numpy as np
    import matplotlib.mlab as mlab
    import matplotlib.pyplot as plt

    ig, ax = plt.subplots()

    sram.errorbitlist_to_xyplot(data, ax)
    plt.show()


if __name__ == "__main__":
    test()


