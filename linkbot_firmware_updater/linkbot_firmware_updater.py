#!/usr/bin/env python3

__version__ = "0.0.3"

import sys
from PyQt4 import QtCore, QtGui
try:
    from linkbot_firmware_updater.dialog import Ui_Dialog
except:
    from dialog import Ui_Dialog
import linkbot
import time
import glob
import threading
import os
import subprocess

import pystk500v2

from functools import reduce

#  idVendor           0x03eb Atmel Corp.
#  idProduct          0x204b LUFA USB to Serial Adapter Project

def _retry(f, n, interval, args=(), kwargs={}):
    retries = 0
    success = False
    while True:
        try:
            return f(*args, **kwargs)
        except:
            retries += 1
            if retries >= times:
                raise
            else:
                time.sleep(interval)

class LinkbotProgrammer(pystk500v2.Stk500):
    WORDSIZE = 2
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flashFile = pystk500v2.HexFile()
        self.eepromFile = pystk500v2.HexFile()
        self.progress = 0.0
        self._isprogramming = False

    def getProgress():
        return self.progress

    def set_device(self, devicecode = 0x86,
                         revision = 0x00,
                         progtype = 0x00,
                         parmode = 0x01,
                         polling = 0x01,
                         selftimed = 0x01,
                         lockbytes = 0x01,
                         fusebytes = 0x03,
                         flashpollval1 = 0xff,
                         flashpollval2 = 0xff,
                         eeprompollval1 = 0xff,
                         eeprompollval2 = 0xff,
                         pagesizehigh = 0x00,
                         pagesizelow = 0x80,
                         eepromsizehigh = 0x04,
                         eepromsizelow = 0x00,
                         flashsize4 = 0x00,
                         flashsize3 = 0x00,
                         flashsize2 = 0x80,
                         flashsize1 = 0x00):
        super().set_device( 
                         devicecode,
                         revision,
                         progtype,
                         parmode,
                         polling,
                         selftimed,
                         lockbytes,
                         fusebytes,
                         flashpollval1,
                         flashpollval2,
                         eeprompollval1,
                         eeprompollval2,
                         pagesizehigh,
                         pagesizelow,
                         eepromsizehigh,
                         eepromsizelow,
                         flashsize4,
                         flashsize3,
                         flashsize2,
                         flashsize1)
    def set_device_ext(self, commandsize = 0x05,
                             eeprompagesize = 0x04,
                             signalpagel = 0xd7,
                             signalbs2 = 0xc2,
                             resetdisable = 0x00):
        super().set_device_ext(commandsize, eeprompagesize, signalpagel,
                               signalbs2, resetdisable)

    def loadFlashHexFile(self, filename):
        self.flashFile.fromIHexFile(filename)

    def loadEepromHexFile(self, filename):
        self.eepromFile.fromIHexFile(filename)

    def loadProgram(self, blocksize=0x0100, eepromblocksize=0x0010):
        self._isprogramming = True
        _retry(self.get_sync, 5, 1)
        self.set_device()
        self.set_device_ext()
        self.enter_progmode()
        signature_bytes = self.read_sign()
        signature = 0
        for b in signature_bytes:
            signature = (signature<<8) + b
        assert signature == 0x1ea701
        # Load the flash program
        curAddr = 0
        while curAddr < len(self.flashFile):
            isBlank = reduce(
                lambda x,y: True if (x==True) and (y==0xff) else False,
                self.flashFile[curAddr:curAddr+blocksize],
                True)
            if not isBlank:
                self.load_address(int(curAddr/self.WORDSIZE))
                self.prog_page('F', self.flashFile[curAddr:curAddr+blocksize])
            curAddr += blocksize
            self.progress = curAddr/len(self.flashFile)
        # Load the eeprom file
        curAddr = 0
        while curAddr < len(self.eepromFile):
            isBlank = reduce(
                lambda x,y: True if (x==True) and (y==0xff) else False,
                self.eepromFile[curAddr:curAddr+eepromblocksize],
                True)
            if not isBlank:
                self.load_address(int(curAddr/self.WORDSIZE))
                self.prog_page('E', self.eepromFile[curAddr:curAddr+eepromblocksize])
            curAddr += eepromblocksize
        self.leave_progmode()
        self._isprogramming = False

    def loadProgramAsync(self, *args, **kwargs):
        self.thread = threading.Thread(target=self.loadProgram, 
                                       args=args,
                                       kwargs=kwargs)
        self.thread.start()
        

from pkg_resources import resource_filename, resource_listdir
fallback_hex_file = ''
fallback_eeprom_file = ''
firmware_files = resource_listdir(__name__, 'hexfiles')
firmware_files.sort()
firmware_basename = os.path.splitext(
    resource_filename(__name__, os.path.join('hexfiles', firmware_files[0])))[0]
fallback_hex_file = firmware_basename + '.hex'

instructions_text = '''<html><head/><body><p>Instructions:</p><p>1. Unplug all
Linkbots and Z-Link dongles connected to your computer.</p><p>2. Turn off the
Linkbot you want to update.</p><p>3. Connect the Linkbot or Z-Link dongle you
want to update to your computer with a USB cable. (Note: Only connect one
Linkbot or Z-Link dongle at a time to update.)</p><p>4. Turn on the Linkbot and
wait until the firmware is updated. If you are updating a Z-Link dongle, you
don't have to turn it on manually; it will turn on as soon as you plug it in in
step 3.</p><p>When the Linkbot beeps and its LED turns blue, you are
done!</p><p>To flash another robot, return to step 1.</p></body></html>'''

programming_text = '''
<html>
<head/>
<body>
<p> The robot is now programming! Please be patient: This process can take a 
few minutes. Once the process is done, the "Close" button will re-enable
itself and the normal instructions will again be displayed in this window...
</p>
</body>
</html>
'''

class StartQT4(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QWidget.__init__(self, parent)
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self.isRunning = True
        self.setWindowTitle('Linkbot Firmware Programmer')

    def accept(self):
        self.waiting_overlay.show()
        #QtCore.QCoreApplication.instance().quit()
        self.startProgramming('/dev/null')

    def reject(self):
        self.isRunning = False
        QtCore.QCoreApplication.instance().quit()

    def distractBaromeshThread(self):
        while self.isRunning:
            linkbot._linkbot.cycleDongle(2)
            time.sleep(1)

    def listenerThread(self):
        prevDevices = glob.glob('/dev/ttyACM*')
        while self.isRunning:
            devices = glob.glob('/dev/ttyACM*')
            if len(devices) > len(prevDevices):
                time.sleep(1.5)
                self.startProgramming((set(devices)-set(prevDevices)).pop())
            prevDevices = devices
            time.sleep(0.5)

    def startProgramming(self, serialPortPath): 
        # Try and find the latest firmware file
        try:
            hexfiles = glob.glob(
                os.environ['HOME'] + 
                '/.local/share/Barobo/LinkbotLabs/firmware/*.hex')
            hexfile = sorted(hexfiles)[-1]
        except:
            try:
                hexfiles = glob.glob(
                    '/usr/share/Barobo/LinkbotLabs/firmware/*.hex')
                hexfile = sorted(hexfiles)[-1]
            except:
                hexfile = fallback_hex_file
        print("Programing hex file:")
        print(hexfile)
        # Make sure EEPROM file also exists
        firmwareDir = os.path.dirname(hexfile)
        firmwareName,_ = os.path.splitext(os.path.basename(hexfile))
        eepromFile = os.path.join(firmwareDir, firmwareName+'.eeprom')
        print(eepromFile)
        if not os.path.exists(eepromFile):
            QtGui.QMessageBox.critical(
                self,
                'Error: EEPROM File Not Found',
                'A firmware file has not been found on this system.')
        try:
            self.ui.label.setText(programming_text)
            self.ui.buttonBox.setEnabled(False)
            self.programmer = LinkbotProgrammer(serialPortPath)
            self.programmer.loadFlashHexFile(hexfile)
            self.programmer.loadEepromHexFile(eepromFile)
            self.programmer.loadProgram()
        except Exception as e:
            print(e)
        self.ui.label.setText(instructions_text)
        self.ui.buttonBox.setEnabled(True)

def main():
    app = QtGui.QApplication(sys.argv)
    myapp = StartQT4()
    myapp.show()
    distractThread = threading.Thread(target=myapp.distractBaromeshThread)
    distractThread.start()

    listenerThread = threading.Thread(target=myapp.listenerThread)
    listenerThread.start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
