#Basic python app for testing/debug

import random
import numpy as np
import chipwhisperer.hardware.naeusb.naeusb as NAE
usb = NAE.NAEUSB()

def do_test():

    #Connecting - need to sign proper drivers shortly
    usb.con(idProduct=[0xC305])

    #Total SRAM size
    test_len = 4194304

    #Generate random test vector (so when re-run know if write was working)
    print "Generating test vector %d bytes"%test_len
    data = np.random.randint(0, 256, test_len)

    print "Writing..."
    #Break into 1024 chunks on write - required to avoid buffer overflow!
    totalsent = 0
    chunksize = 1000
    if len(data) < chunksize:
        usb.cmdWriteMem(0, data)
        totalsent += len(data)
    else:
        lastendaddr = 0
        for chunkstart in range(0, len(data), chunksize):
            lastendaddr = (chunkstart + chunksize)
            chunk = data[chunkstart:lastendaddr]
            usb.cmdWriteMem(chunkstart, chunk)        
            totalsent += len(chunk)

        if totalsent != len(data):
            chunk = data[lastendaddr:]
            usb.cmdWriteMem(lastendaddr, chunk)

    raw_input("Hit Enter once Glitch inserted")

    print "Reading..."

    din = []
    din = usb.cmdReadMem(0, test_len)
    
    errorcnt = 0

    errorlist = []

    for i in range(0, test_len):
        if data[i] != din[i]:
            errorlist.append(0xff)
            errorcnt += 1
        else:
            errorlist.append(0)
    print "Errors: %d (of %d)"%(errorcnt, test_len)

    with open("error_location.bin", "wb") as errfile:
        errfile.write(bytearray(errorlist))

    usb.close()

while True:
    do_test()

#do_test()
