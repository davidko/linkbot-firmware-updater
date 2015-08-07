#!/usr/bin/env python3

__version__ = "0.0.2"

import sys
from PyQt4 import QtCore, QtGui
from linkbot_firmware_updater.dialog import Ui_Dialog
import linkbot
import time
import glob
import threading
import os
import subprocess

#  idVendor           0x03eb Atmel Corp.
#  idProduct          0x204b LUFA USB to Serial Adapter Project

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
            hexfile = hexfiles[-1]
        except:
            try:
                hexfiles = glob.glob(
                    '/usr/share/Barobo/LinkbotLabs/firmware/*.hex')
                hexfile = hexfiles[-1]
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
            cmd = [
              'avrdude', 
              '-c',
              'arduino', 
              '-P',
              serialPortPath,
              '-p',
              'm128rfa1',
              '-q',
              '-e',
              '-V',
              '-U',
              'fl:w:{0}'.format(hexfile),
              '-U',
              'eeprom:w:{0}'.format(eepromFile),
              '-b',
              '57600']
            self.myprocess = subprocess.Popen(cmd)
            self.myprocess.wait()
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
