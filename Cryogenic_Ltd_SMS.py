# Cryogenic Ltd. SMS driver for the cryogenic superconducting
# magnet system current source.

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
import re
import qt
import time

class Cryogenic_Ltd_SMS(Instrument):
    '''
    This is the python driver for the cryogenic limited superconducting
    magnet system.

    
    Usage:
    <name> = Cryogenic_Ltd_SMS('<name>', <SMS_address>)
    '''
    def __init__(self, name, address=None):
        
        Instrument.__init__(self, name, tags=['measure'])
        self._visains = visa.instrument(address)
        self._visains.term_chars = '\r\n'
        
        self.add_parameter('field', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            units='T', format='%.3f',
                            minval=-8.0, maxval=8.0)
        self.add_parameter('current', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            minval=-120.0, maxval=120.0, units='A',
                            format='%2.3f')
        self.add_parameter('ramprate', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            minval=0.0, maxval=5.0, units='A/s',
                            format='%.3f')
        self.add_parameter('heater', type=types.IntType,
                            flags=Instrument.FLAG_GETSET,
                            format_map={0:'off', 1:'on'})
        self.add_parameter('heater_voltage', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            units='V',minval=0.0, maxval=8.0,
                            doc='''Default switch voltage at 4.2K => 2V.''')
        self.add_parameter('field_constant', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            minval=0.0, maxval=0.5, units='T/A',
                            format='%.6f')
        self.add_parameter('He_level', type=types.FloatType,
                            flags = Instrument.FLAG_GET,
                            units='mm', format='%.1f')
        self.add_parameter('persistent_current', type=types.FloatType,
                            flags = Instrument.FLAG_GET,
                            units='A',format='%.2f')
        self.add_parameter('voltage', type=types.FloatType,
                            flags=Instrument.FLAG_GET,units='V',
                            format='%.1f')
        self.add_parameter('voltage_limit', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET, units='V',
                            minval=0.0, maxval=5.0, format= '%.1f')
        self.add_parameter('mode', type=types.IntType,
                            flags=Instrument.FLAG_GETSET, 
                            format_map = {0:'Resistive', 1:'Persistent'})
        
        self._visains.ask('TESLA OFF')
        self._visains.ask('SET MID 0.0')
        
        # Some factory defaults here:
        self._default_heater_voltage = 2.0
        self._field_constant = 0.074418
        self._He_threshold = 100
        
        self.set_heater_voltage(self._default_heater_voltage)
        self.set_field_constant(self._field_constant)
        
        self._mode = None
        try:
            self.get_all()
        except:
            self.clear_buffer()
            self.get_all()
        

    
    # ---------------------------------------------------------------------------  
    # functions
    # ---------------------------------------------------------------------------  
    
    def get_all(self):
        '''
        Gets the values of all parameters.
        '''
        self.get_field_constant()
        self.get_current()
        self.get_field()
        self.get_ramprate()
        self.get_heater()
        self.get_heater_voltage()
        self.get_He_level()
        mode = self.get_mode()
        if mode == 1:
            self.get_persistent_current()
        self.get_voltage()
        self.get_voltage_limit()

    def clear_buffer(self):
        '''
        Clears the buffer of the magnet supply,
        for use to restablish communications after
        a quench.
        '''
        answer = True
        while answer:
            try:
                self._visains.ask('')
            except:
                answer=False
        print '%s: Buffer cleared.' % self.get_name()
        
    def _get_I(self):
        ans = self._visains.ask('GET OUTPUT')
        #print ans
        rx = re.compile( r'\d+\.\d+')
        anslist = rx.findall(ans)
        #print anslist
        I = float(anslist[0])
        return I
    
    def _set_I(self, value):
        '''
        Ramp the current to a new value. Not for individual use,
        use, set_current instead.
        Input:
            value (float)       :  Current value to set, in amps.
        Output:
            None
        '''
        name = self.get_name()
        if value == 0.0:
            self._visains.write('RAMP ZERO')
        else:
            self._visains.ask('SET MAX %6.6f' % value)
            self._visains.write('RAMP MAX')
        
        timestep = 0.2
        ramping = True
        while ramping:
        
            try:
                ans = self._visains.ask('RAMP STATUS')
            except:
                ans = 'possible QUENCH'
                
            ramping = False
            if 'RAMPING' in ans:
                qt.msleep(timestep)
                ramping = True
            if 'QUENCH' in ans:
                mytime = time.strftime("%a, %d %b %Y %H:%M:%S", time.localtime())
                print '%s: Magnet quench detection tripped!' % name
                print '%s: Time of quench: %s.' % (name, mytime)
                print '%s: Field ramped to zero.' % name
                qt.msleep(180)
                ramping = False
                return False
        return True
        
    def _get_polarity(self):
        '''
        This function reads the polarity
        '''
        #ans = self._visains.ask('DIRECTION')
        ans = self._visains.ask('GET SIGN')
        if 'NEGATIVE' in ans:
            return -1.0
        elif 'POSITIVE' in ans:
            return 1.0
        else:
            return 1.0
        
    def _set_polarity(self, value):
        '''
        This function sets the polarity.
        input:
            value (float)   :   1 for positive
                                -1 for negative
        '''
        if value == 1.0 or value == 0.0:
            str = '+'
        elif value == -1.0:
            str = '-'
        ans = self._visains.write('DIRECTION %s' % str)
        
    def convert_field(self, field):
        '''
        Convert a value given in T to a current to set
        on the magnet_supply, in A. Be sure to check that
        the magnet conversion function is set properly
         
        Input:
            field (float)   :    field value to convert
         
        Output:
            current (float) :    corresponding current value
        '''
        fc = self.get_field_constant()
        return field/fc
       
    def ask(self, command):
        return self._visains.ask(command)
        
    def _safety_get_level(self):
        level = self.get_He_level()
        name = self.get_name()
        # Safety message if the He level gets too low.
        if (level < self._He_threshold) and (level != 0.0):
            current = self._get_I()
            pers_current = self.get_persistent_current()
            
            if current > 0.1 and pers_current == 0.0:
                print '%s: He level dangerously low! Recommend to de-energize magnet.' % name
            elif current < 0.1 and pers_current == 0.0:
                print '%s: He level too low for safe magnet operation. Recommend to leave magnet de-energized.' % name
            if pers_current != 0.0:
                print '%s: He level dangerously low with persistent current of %2.2fA running. Recommend to de-energize magnet.' % (name, pers_current)
                
    
    # ---------------------------------------------------------------------------    
    # Get and set parameters   
    # ---------------------------------------------------------------------------        
    
    def do_set_mode(self, mode):
        if mode == self._mode:
            return True
        name = self.get_name()
        
        if mode == 1:
            # Changing to persistent mode
            current = self.get_current()
            if self.get_heater() == 0:
                if self.get_persistent_current() != 0.0:
                    print '%s: Heater is already turned off, magnet in persistent mode.' % name
                    self._mode = mode
                    return True
                if self.get_current() == 0:
                    print '%s: Unable to switch to persistent mode while current is zero. Aborting' % name
                    return None
            print '%s: Engaging persistent mode at I = %.2fA.' % (name, current)
            print '%s: Please wait.' % name
            qt.msleep(45)
            self.set_heater('off')
            qt.msleep(60)
            Ip = self.get_persistent_current()
            self._set_I(0)
            self.get_current()
            print '%s: Persistent mode engaged. Ipersist = %.2fA.' % (name, Ip)
            self._mode = mode
            return True
            
        elif mode == 0:
            if self.get_heater() == 1:
                print '%s: Heater already turned on, magnet in resistive mode.' % name
                self._mode = mode
                return True
            current = self.get_persistent_current()
        
            print '%s: Disengaging persistent mode at Ipersist = %.2fA.' % (name, current)
            print '%s: Please wait.' % name        
            pol = np.sign(current)
            self._set_polarity(pol)
            self._set_I(np.abs(current))
            qt.msleep(1)
            self._visains.ask('HEATER 1')
            qt.msleep(30)
            self.get_persistent_current()
            curr = self.get_current()
            self.get_heater()
            print '%s: Persistent mode disengaged. I = %.2fA.' % (name, curr)
            self._mode = mode
            return True
    
    def do_get_mode(self):
        if self._mode is not None:
            return self._mode
        else:
            if self.get_persistent_current() != 0.0 and self.get_heater() == 0:
                self._mode = 1
                return 1
            else:
                self._mode = 0
                return 0
    
    def do_get_current(self):
        '''
        Returns the signed value of the magnet current.
        
        Input:
            None
        Output:
            current (float)     : Absolute value of the magnet
                                  current in Amps.
        '''
        I = self._get_I()
        pol = self._get_polarity()
        self.get_voltage()
        return I*pol
    
    def do_set_current(self, val):
        '''
        Sets the value and sign of the magnet current.
        
        Input:
            current (float)     : Value of the magnet
                                  current in Amps.
        Output:
            None
        '''
        self._safety_get_level()
        Iold = self.get_current()
        pold = np.sign(Iold)
        mode = self.get_mode()
        
        if mode == 1:
            print '%s: Unable to change current while in persistent mode! Change to resistive mode first.' % self.get_name()
            return None
        if self.get_heater() == 0:
            print '%s: Unable to change current while switch heater is off! Turn heater on first.' % self.get_name()
            return None
            
        if val != 0:
            pnew = np.sign(val)
        else:
            pnew = pold
        
        if pold != pnew:
            # If we have to switch magnet polarity, ramp to zero first
            self._set_I(0)
            self._set_polarity(pnew)
        current_set = self._set_I(abs(val))
        self.get_voltage()
        if not current_set:
            self.get_current()
        return current_set
        
    def do_get_field(self):
        mode = self.get_mode()
        if mode == 0:
            I = self.get_current()
        elif mode == 1:
            I = self.get_persistent_current()
        if self.get_field_constant() != 0.0:
            return self.get_field_constant()*I
        else:
            print '%s: No field constant defined, unable to get field.' % self.get_name()
            return 0.0

    def do_set_field(self, field):
        if self.get_field_constant() != 0.0:
            I = self.convert_field(field)
            return self.set_current(I)
        else:
            print '%s: No field constant defined, unable to set field.' % self.get_name()
            return False
        
    def do_get_ramprate(self):
        ans = self._visains.ask('GET RATE')
        rx = re.compile( r'\d+\.\d+')
        anslist = rx.findall(ans)
        rate = anslist[0]
        return float(rate)
     
    def do_set_ramprate(self, value):
        '''
        Sets the ramprate of the magnet.
        Note that the magnet only has 64 discrete
        ramprates that are permitted. Whatever you
        enter here is automatically rounded of to
        the nearest allowed rate value.
        '''
        command = 'SET RAMP %.4f' % value
        return self._visains.ask(command)
        
    def do_set_heater_voltage(self, value):
        command = 'SET HEATER %.3f' % value
        self._visains.ask(command)
    
    def do_get_heater_voltage(self):
        ans = self._visains.ask('GET HV')
        rx = re.compile( r'\d+\.\d+')
        anslist = rx.findall(ans)
        hv = anslist[0]
        return float(hv)

    def do_get_He_level(self):
        # Helium level meter is quite noisy, so
        # we average over 10 values to get an
        # accurate reading.
        levels = []
        for x in np.arange(0,10):
            ans = self._visains.ask('GET LEVEL')
            for part in ans.split():
                if part.isdigit():
                    level = int(part)
            levels.append(level)
        level = np.mean(levels)
        # Convert level to the level in the green cryostat.
        # Not sure if this is needed, test first!
        #level = level*0.002/(2.55/320)
        return level
    
    def do_get_field_constant(self):
        ans = self._visains.ask('GET TPA')
        rx = re.compile( r'(\d+\.\d+)|(\s.\d+)')
        anslist = rx.findall(ans)
        try:
            fc = anslist[0][1]
            if fc[0] == ' ':
                fc = fc.strip()
                fc = '0'+fc
        except:
            fc = 0.0
        return float(fc)
    
    def do_set_field_constant(self, val):
        ans = self._visains.ask('SET TPA %.7f' % val)
    
    def do_set_heater(self, val):
        '''
        Switches the heater on (1) or off (0).
        '''
        if self.get_mode() == 1:
            print '%s: Unable to change heater while in persistent mode.' % self.get_name()
            return None
        self._visains.ask('HEATER %i' % val)
            
    def do_get_heater(self):
        ans = self._visains.ask('HEATER')
        if 'ON' in ans:
            return 1
        elif 'OFF' in ans:
            return 0
            
    def do_get_persistent_current(self):
        if self.get_heater() == 1:
            return 0.0
        #try:
         #   ans = self._visains.ask('GET PER')
          #  rx = re.compile( r'[\s,-]\d+\.\d+')
          #  anslist = rx.findall(ans)
          #  pc = anslist[0]
        #except:
         #   pc = 0.0
        # To get the proper sign, use the update command:
        ans = self._visains.ask('UPDATE')
        answer = True
        heater_off = False
        linecount = 0
        while answer and linecount <= 11:
            try:
                ansline = self._visains.read()
            except:
                ansline = ''
                answer = False
            if 'HEATER STATUS: SWITCHED OFF AT' in ansline:
                rx = re.compile( r'[\s,-]\d+\.\d+')
                anslist = rx.findall(ansline)
                heater_off = True
            elif 'HEATER STATUS: OFF' in ansline:
                anslist = [0.0]
            linecount += 1
        if heater_off:
            pc = anslist[0]
            return float(pc)
        else:
            return 0.0
        
    def do_get_voltage(self):
        ans = self._visains.ask('GET OUTPUT')
        rx = re.compile( r'\d+\.\d+')
        anslist = rx.findall(ans)
        try:
            V = float(anslist[1])
        except:
            V = 0.0
        return V
        
    def do_get_voltage_limit(self):
        ans = self._visains.ask('GET VL')
        rx = re.compile( r'\d+\.\d+')
        anslist = rx.findall(ans)
        vl = anslist[0]
        return vl
        
    def do_set_voltage_limit(self, val):
        command = 'SET LIMIT %.2f' % val
        return self._visains.ask(command)