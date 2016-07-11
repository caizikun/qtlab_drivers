# Trinamic_pd42_TMCL.py driver for  Trinamic stepper motor and
# rotatable sample holder
# Ludo Cornelissen, 2015
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA
from instrument import Instrument
import types
import visa
import numpy as np
import qt

class Trinamic_pd42_TMCL(Instrument):
    def __init__(self, name, address=None):
    
        Instrument.__init__(self, name, tags=['measure'])
        self._visains = visa.instrument(address)
        self._visains.data_bits = 8
        self._visains.baud_rate = 9600
        self._visains.stop_bits = 1
        self._visains.parity = 0
        self._visains.flow_control = 0
        self._visains.term_chars = '\r'
        
        self.add_function('calibrate')
        self.add_function('get_all')
        self.add_function('manual_calibration')
        
        self.add_parameter('position', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            minval=-140.0, maxval=140, units='degrees',
                            format = '%.2f',
                            doc='''Sample position in degree.\nMinimum step size is 7e-3 degrees. ''')
        self.add_parameter('speed', type=types.FloatType,
                            flags = Instrument.FLAG_GETSET,
                            minval = 2.5, maxval = 10,
                            units = '%',
                            format = '%.2f',
                            doc='''Maximum motor speed in percent of full speed.\n1% is approx 1.6 deg/sec.''')
        self.add_parameter('calibrated', type=types.BooleanType,
                            flags = Instrument.FLAG_GET,
                            doc='''Calibration has been performed (True) or not (False)''')
        self.add_parameter('standby_current', type=types.IntType,
                            flags = Instrument.FLAG_GETSET,
                            minval = 0, maxval = 255,
                            format = '%i',
                            doc='''Current the motor uses when not rotating. A value of 255 corresponds to 2A (rms). Default is 20.''')
        self.add_parameter('active_current', type=types.IntType,
                            flags = Instrument.FLAG_GETSET,
                            minval = 1, maxval = 255,
                            format = '%i',
                            doc='''Current the motor uses to rotate. A value of 255 corresponds to 2A (rms). Default is 180.''')
        self._speed = 3
        self.set_speed(self._speed)
        self._position = None
        self.disable_limits()
        self._calibrated = False
        # Set the standby current parameters:
        self._standby_current = 20
        self._active_current = 180
        
        # Switch motor to standby current 20ms after reaching position.
        self._visains.write(self.convert_to_valid_hex_instr(5,214,2))
        
        # Standby current is set to very low value! to avoid interference with the measurements.
        self._visains.write(self.convert_to_valid_hex_instr(5,7,self._standby_current))
        
        # Max motor current is set to 4/5 of the absolute maximum value to be able to provide large torques
        self._visains.write(self.convert_to_valid_hex_instr(5,6,self._active_current))
        
        self.get_all()
        
# functions
    def get_all(self):
        ''' Get all parameter values '''
        self.get_speed()
        self.get_calibrated()
        self.get_position()
        self.get_standby_current()
        self.get_active_current()
        
    def _tohex(self, val, nbits=32):
        '''
        Convert value to 32bit hexadecimal representation.
        Uses 2's complement rule for negative values.
        '''
        hexval = hex((val + (1 << nbits)) % (1 << nbits)).strip('L')     
        return hexval
        
    def _padhexa(self, s):
        '''
        fill a hexadecimal string up to 8 numbers.
        '''
        return '0x' + s[2:].zfill(8)
    
    def convert_to_valid_hex_instr(self, instruction, type, value):
        '''
        Converts an instruction, type, value triplet to a valid
        hexadecimal command for sending to the motor.
        '''
        # always address motor 0 on address 1
        address = 1
        motor = 0
        # First 4 bytes of the 9byte command
        byte_list = [address, instruction, type, motor]
        # nasty business with generating hex numbers
        my_hex = self._tohex(value)
        # add padding for positive hex values:
        sign = np.sign(value)
        if sign != -1:           
            my_hex = self._padhexa(my_hex)
        
        # calculate the checksum in a very ugly way but it works
        valuelist = []        
        for count in np.arange(2,10,2):
            myval = '0x'+my_hex[count:count+2]
            valuelist.append(int(myval,16))
             
        byte_list = byte_list+valuelist
        checksum = sum(byte_list)
        # checksum is modulo 256
        last_byte = checksum % 256
        # byte_list is now a 9-byte command list
        byte_list.append(last_byte)
        strlist = [chr(x) for x in byte_list]
        str = ''.join(strlist)
        return str 
    
    def enable_limits(self):
        '''
        Turn on the limit switches of the stepper motor.
        '''
        str1 = self.convert_to_valid_hex_instr(5,12,0)
        str2 = self.convert_to_valid_hex_instr(5,13,0)
        self._visains.write(str1)
        self._visains.write(str2)
        
    def disable_limits(self):
        '''
        Turn off the limit switches of the stepper motor.
        
        Use only for debugging purposes!
        '''
        str1 = self.convert_to_valid_hex_instr(5,12,1)
        str2 = self.convert_to_valid_hex_instr(5,13,1)
        self._visains.write(str1)
        self._visains.write(str2)    
    
    def stop(self):
        '''
        Stops motor movement.
        '''
        str = self.convert_to_valid_hex_instr(3, 0, 0)
        self._visains.write(str)
    
    def _get_position(self):
        ''' Get the current motor position '''
        return self._position
        
    def _set_position(self, angle):
        ''' 
        Rotate the stepper motor 
        Input:
            angle (float)   :  angle to rotate to.
        Output:
            None
        '''
        substeps = 256
        angle_per_step = 1.8
        steps = int(substeps/angle_per_step*angle)
        # convert to a valid hexadecimal instruction
        str = self.convert_to_valid_hex_instr(4, 0, steps)
        # write to motor
        self._visains.write(str)
        pos = self._get_position()
        if pos is not None:
            if np.sign(pos*angle) != -1:
                deltaA = np.abs(pos - angle)
            else:
                deltaA = np.abs(pos)+np.abs(angle)
            sleep_time = deltaA/(self.get_speed()*4.2)
        else:
            sleep_time = 360/(self.get_speed()*4.2)
        qt.msleep(sleep_time)    
        self._position = angle
    
    def calibrate(self):
        '''
        Calibrates the stepper motor automatically, using
        the left and right end switches.
        '''
        # Set the reference search to the right mode: now searches
        # for the right and the left limit switch, and then sets the
        # zero in the middle of these two switches.
        pos = self.get_position()
        if pos is not None:
            if pos >= 0.0:
                search_mode = 5
            else:
                search_mode = 6
        else:
            search_mode = 5
        self._visains.write(self.convert_to_valid_hex_instr(5,193,search_mode))
        # increase the speed a bit to limit waiting time
        old_speed = self.get_speed()
        speed = 6.0
        self._visains.write(self.convert_to_valid_hex_instr(5,194,int(2047.0/100.0*speed)))
        name = self.get_name()
        
        print '%s: Starting motor calibration by automated reference search.' % name
        ans = raw_input('%s: Press y to continue, any other key to abort.' % name)
        if ans == 'y': 
            #self.enable_limits()
            # start the search
            self._visains.write(self.convert_to_valid_hex_instr(13,0,0))
            print '%s: Calibrating...' % name
            # wait sufficiently long for the search to finish. 
            
            qt.msleep(720/(speed*4.2))            
            print '%s: Reference search completed succesfully.' % name
            # Reset the motor position to equal 0 on the home switch:
            self._position = 0
            self._visains.write(self.convert_to_valid_hex_instr(5,1,0))
            self._calibrated = True
            
            # Short check if zero is really zero, and we are running
            # through home switch smoothly.
            self.set_position(5)
            self.set_position(-5)
            self.set_position(0)
            print '%s: Sample at 0 degrees.' % name
            self.set_speed(old_speed)
            
            self.disable_limits()
            
            return True
            
        else:
            return False
    
    def manual_calibration(self):
        '''
        Manually calibrates the sample holder. Note: this function
        can override the current motor calibration. Functions asks for
        user input of the actual sample position (angle in degrees).
        '''
        name = self.get_name()
        print '%s: Starting manual calibration procedure.' % name
        ans = raw_input('%s: Press y to continue, any other key to abort.' % name)
        if ans == 'y':
            print '%s: Please enter current sample position.' % name
            pos = raw_input('%s: Sample angle in degrees:' % name)
            try:
                pos = float(pos)
                print 'Calibrated to %f degrees.' % pos
            except:
                print '%s: Invalid position, procedure aborted.' % name
                return None
            
            # Override the current motor position for the new value input by the user
            angle = -pos*2.5
            substeps = 256
            angle_per_step = 1.8
            steps = int(substeps/angle_per_step*angle)
            self._visains.write(self.convert_to_valid_hex_instr(5,1,steps))
        else:
            print '%s: Procedure aborted.' % name
            return False
        self._position = -pos*2.5
        self.get_position()
        self._calibrated = True
        self.get_calibrated()
        return True
            
    
# Get and set parameters            
    def do_get_position(self):
        ''' 
        Get the current sample position in degrees.
        Input:
            None
        Output:
            angle (float)    : sample angle in degrees.
        '''
        pos = self._get_position()
        if pos != None:
            pos = -self._get_position()/2.5
        return pos
        
    def do_set_position(self, angle):
        ''' 
        Set the current sample position in degrees.
        Input:
            angle (float)       : angle to rotate to.
        Output:
            None
        '''
        name = self.get_name()
        if self.get_calibrated():
            self._set_position(-angle*2.5)
        else:
            print '%s: unable to set position without proper motor calibration.' % name
            print '%s: please run %s.calibrate() first.' % (name, name)
    
    def do_set_speed(self, speed):
        '''
        Set the rotation speed of the motor.
        In percentage of full motor speed. 
        10% is approximately 42 deg/sec
        5% is approx. 21 deg/sec
        Input:
            speed (float)     :  rotation speed in %.
        Output:
            None.
        '''
        value = int(2047.0/100.0*speed)
        str = self.convert_to_valid_hex_instr(5,4,value)
        self._visains.write(str)
        self._speed = speed
    
    def do_get_speed(self):
        '''
        Returns current maximum motor speed in % of full scale.
        Input:
            None
        Output:
            speed (float)   : speed in %.
        '''
        return self._speed
        
    def do_get_calibrated(self):
        '''
        Returns whether the stepper motor has been properly calibrated.
        '''
        return self._calibrated
        
    def do_set_standby_current(self, val):
        '''
        Sets the standby current of the sample holder. This is the
        current that is provided to the motor when it is standing still.
        Can be a value between 0 and 255.
        '''
        val = int(val)
        self._visains.write(self.convert_to_valid_hex_instr(5,7,val))
        self._standby_current = val
        
    def do_get_standby_current(self):
        '''
        Returns the motor standby current.
        '''
        return self._standby_current
        
    def do_set_active_current(self, val):
        '''
        Sets the standby current of the sample holder. This is the
        current that is provided to the motor when it is standing still.
        Can be a value between 0 and 255.
        '''
        val = int(val)
        self._visains.write(self.convert_to_valid_hex_instr(5,6,val))
        self._active_current = val
    
    def do_get_active_current(self):
        '''
        Returns the motor active current
        '''
        return self._active_current