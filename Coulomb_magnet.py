# Coulomb magnet.py driver for the magnet current source of the Coulomb
# Setup
# Ludo Cornelissen, 2014

# Because the setup is weird, two instruments are required to control
# the field: the Keithley 230 voltage source and the GMW current
# reversal switch (CRS). The CRS controls the magnitude of the current
# and the Keithley is used to trigger current reversal by sending
# a voltage pulse to some relay.

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
from time import sleep
import scipy.optimize
import re
import qt

class Coulomb_magnet(Instrument):
    '''
    This is the python driver for the magnet of the Coulomb setup.
    Since the switching mechanism is a bit weird, this magnet requires two
    instruments to function. A keihtley voltage source which is used to 
    control a relay, which can reverse the current polarity through the
    current reversal switch (CRS). The CRS also controls the magnet current.
    
    Usage:
    <name> = Coulomb_magnet('<name>', <CRS_address>, <Keithley_address>)
    '''
    def __init__(self, name, CRS_address=None, Keithley_address=None):
        
        Instrument.__init__(self, name, tags=['measure'])

        self._CRS = CRS_address
        self._visainsCRS = visa.instrument(CRS_address)
        self._Keithley = Keithley_address
        self._visainsKeithley = visa.instrument(Keithley_address)
        
        self._visainsCRS.term_chars = '\n'
        
        self.add_function('get_all')
        self.add_function('ramp_current')
        self.add_function('convert_field')

        self.add_parameter('conversion_function', type=types.StringType,
                           flags=Instrument.FLAG_GETSET)
        self.add_parameter('polarity', type=types.IntType,
                            flags=Instrument.FLAG_GETSET,
                            minval=-1, maxval=1, units='1/-1')
        self.add_parameter('field', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            units='T', format='%.3f')
        self.add_parameter('current', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            minval=0.0, maxval=75.0, units='A',
                            format='%2.3f')
        self.add_parameter('ramprate', type=types.FloatType,
                            flags=Instrument.FLAG_GETSET,
                            minval=0.0, maxval=5.0, units='A/s')
        
        # Initialize the conversion function and the ramprate
        self._conversion_function = 'B=0.0177*I-7.39e-7*I^3'
        self._ramprate = 1.0
        
        # Turn on Keithley output to be sure the polarity switching is
        # functioning
        self._visainsKeithley.write('I2X\r\n')
        
        # Get actual values of field and current.
        self.get_all()
    
    # ---------------------------------------------------------------------------  
    # functions
    # ---------------------------------------------------------------------------  
    
    def get_all(self):
        '''
        Gets the values of all parameters.
        '''
        self.get_conversion_function()
        self.get_current()
        self.get_field()
        self.get_ramprate()
        self.get_polarity()
                      
    def ramp_current(self, value):
        '''
        Ramp the current to a new value. Takes both
        positive and negative values for the current. Use this function
        to change the magnet current, instead of set_current.
        
        Input:
            value (float)       :  Current value to set, in amps.
        Output:
            None
        '''
        I_old = self.get_current()
        polarity = self.get_polarity()
        I_old = I_old*polarity
        
        I_new = value
        # Set a timestep for the current ramping
        timestep = 1.0
        # Calculate the current step to take using the user defined ramprate
        # We divide the field ramprate by the conversion factor
        delta_I = timestep*self.get_ramprate()
        
        test = np.abs(I_new - I_old) > delta_I
        if test:
            steps = np.abs( np.ceil( (I_new-I_old) / delta_I ) )
            values = np.linspace(I_old, I_new, steps)
        else:
            values = [I_new]
        
        
        for x in values:
            # First check and set the proper polarity (i.e. reverse
            # only if needed.
            if x < 0 and polarity > 0:
                self.set_polarity(-1)
                polarity = -1
            elif x > 0 and polarity < 0:
                self.set_polarity(1)
                polarity = 1
            # Then set the current.
            qt.msleep(timestep/2.0)
            self.set_current(np.abs(x))
            self.get_field()
            qt.msleep(timestep/2.0) 
        
        qt.msleep(timestep)
        self.get_current()
        self.get_field()

    def write_CRS(self, command):
        '''
        directly write a command to the current reversal switch.
        '''
        self._visainsCRS.write(command)
    
    def ask_CRS(self, query):
        '''
        directly query the CRS.
        '''
        answer = self._visainsCRS.ask(query)
        return answer
    
    def _switch_polarity(self):
        '''
        This function switches the polarity. Used as a helper
        function for do_get_polarity.
        '''
        self._visainsKeithley.write('F1X\r\n')
        sleep(1.0)
        self._visainsCRS.write('TW21\r\n')
        sleep(2.0)
        self._visainsKeithley.write('V24.0X\r\n')
        sleep(3.0)
        self._visainsCRS.write('TW20\r\n')
        sleep(2.0)
        self._visainsKeithley.write('V0.0X\r\n')
        
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
        def conversion_f(I, a, b, B):
            # This is a subfunction defining the relation between current and field
            # It implements B = a*I + b*I^3
            return a*I + b*I**3 - B
        
        def d_conv_f(I, a, b, B):
            # This is a subfunction defining derivative of the conversion function
            # Used in the root finding algorithm to increase robustness
            return a + 3*b*I**2
        
        # get the conversion function
        conv_func = self.get_conversion_function()
        if conv_func == '0.01274*I-4.7e-7*I^3':
            a = 0.01274
            b = -4.7e-7
        elif conv_func == 'B=0.0240*I-1.50e-6*I^3':
            a = 0.024
            b = -1.50e-6
        elif conv_func == 'B=0.0177*I-7.39e-7*I^3':
            a = 0.0177
            b = -7.39e-7
        else:
            print 'Error converting field to current. Verify conversion function.'
            return 0.0
         
        estimate = field/a
        # Use the newton-rhapson root finding algorithm to get the current from the
        # desired value of the field.  
        current = scipy.optimize.newton(conversion_f, x0=estimate, fprime=d_conv_f,
                                        args=(a, b, field), maxiter=200)
        return current
    
    def _get_conversion_factor(self):
        '''
        Extracts the linear coefficient of the current-to-field
        conversion function.
        '''
        conv_func = self.get_conversion_function()
        pat1 = re.compile('\d+.\d+\**I[^\^]')
        first_order = pat1.findall(conv_func)[0]
        pat2 = re.compile('\d+.\d+')
        conv_factor = pat2.match(first_order).group()
        return float(conv_factor)
        
    # ---------------------------------------------------------------------------    
    # Get and set parameters   
    # ---------------------------------------------------------------------------        
    
    def do_get_current(self):
        '''
        Returns the absolute value of the magnet current.
        
        Input:
            None
        Output:
            current (float)     : Absolute value of the magnet
                                  current in Amps.
        '''
        output = self._visainsCRS.ask('R1\r\n')
        try:
            output = np.abs(float(output))
        except:
            output = 0.0
            
        I = output * (75.5/16383.0)
        return I
    
    def do_set_current(self, val):
        '''
        Sets the absolute value of the magnet current.
        Not meant for direct use! Better use the function
        ramp_current
        
        Input:
            current (float)     : Absolute value of the magnet
                                  current in Amps.
        Output:
            None
        '''
        set_val = int((16383.0/75.5)*np.abs(val))
        str = 'W%i\r\n' % set_val
        self._visainsCRS.write(str)
        
    def do_get_conversion_function(self):
        return self._conversion_function
     
    def do_set_conversion_function(self, val):
        conv_funcs = ['0.01274*I-4.7e-7*I^3', 'B=0.0240*I-1.50e-6*I^3',
                      'B=0.0177*I-7.39e-7*I^3']
        if val not in conv_funcs:
            print 'Invalid conversion function! Valid options are:'
            for item in conv_funcs:
                print item
            print 'Error setting conversion function.'
        else: 
            self._conversion_function = val
    
    def do_get_polarity(self):
        '''
        Queries the polarity of the magnet source.
        
        Input:
            None
        Output:
            polarity (int)  :   Current magnet polarity
        '''
        state = self._visainsCRS.ask('TR3\r\n')
        try:
            state = float(state)
        except:
            state = 0.0
            print 'Error reading magnet polarity'
        if state == 1.0:
            polarity = -1
        elif state == 0.0:
            polarity = 1
        else:
            print 'Error reading CRS state.'
            print 'Returned state = %d' % state
            polarity = 1
        return polarity
    
    def do_set_polarity(self, val):
        '''
        Sets the magnet polarity to either 1 or -1.
        
        Input:
            value (int)     :   Polarity to set. Can be
                                either 1 or -1.
        Output:
            None
        '''
        polarity = self.get_polarity()
        if polarity*val > 0:
            return
        else:
            self._switch_polarity()
        
    def do_get_field(self):
        return self._get_conversion_factor() * self.get_current()

    def do_set_field(self, field):
        current = self.convert_field(value)
        self.ramp_current(current)
        
    def do_get_ramprate(self):
        return self._ramprate
     
    def do_set_ramprate(self, value):
        self._ramprate = value
    
