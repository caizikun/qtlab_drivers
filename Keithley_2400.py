# Keithley_2400.py, driver for Keithley 2400 SMU

# Based on:
# Keithley_2100.py driver for Keithley 2100 DMM
# Pieter de Groot <pieterdegroot@gmail.com>, 2008
# Martijn Schaafsma <qtlab@mcschaafsma.nl>, 2008
# Reinier Heeres <reinier@heeres.eu>, 2008 - 2010
#
# Adapted for Keithley 2400 SMU January 2016:
# Ludo Cornelissen <ludo.cornelissen@gmail.com>
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
import visa
import types
import logging
import numpy
import numpy as np
from time import sleep
import qt

class Keithley_2400(Instrument):
    
    def __init__(self, name, address, reset=False):
        '''
        Initializes the Keithley_2400, and communicates with the wrapper.

        Input:
            name (string)           : name of the instrument
            address (string)        : GPIB address
            reset (bool)            : resets to default values
        Output:
            None
        '''
        Instrument.__init__(self, name, tags=['physical'])
        self._visainstrument = visa.instrument(address)
        self._trigger_sent = False
        
        self.add_parameter('source_mode', flags=Instrument.FLAG_GETSET, 
            type=types.IntType, format_map={0:'VOLT', 1:'CURR'})
        self.add_parameter('sense_mode',
            flags=Instrument.FLAG_GETSET,
            type=types.IntType, 
            format_map={0:'VOLT', 1:'CURR', 2:'RES'})
#        self.add_parameter('digits',
#            flags=Instrument.FLAG_GETSET,
#            units='#', minval=4, maxval=7, type=types.IntType)
        self.add_parameter('sense_value', flags=Instrument.FLAG_GET,
            units='V',
            type=types.FloatType,
            tags=['measure'],
            format='%.4e')
        self.add_parameter('sense_range', flags=Instrument.FLAG_GETSET,
            units='V',
            type=types.FloatType,
            format='%.2e')
        self.add_parameter('autorange', flags=Instrument.FLAG_GETSET,
            type=types.IntType, format_map={0:'off', 1:'on'},
            doc='''Enable/disable sense autoranging.''')
        self.add_parameter('source_value', flags=Instrument.FLAG_GETSET,
            units='V',
            type=types.FloatType, tags=['sweep'],
            format='%.4e')
        self.add_parameter('source_compliance', flags=Instrument.FLAG_GETSET,
            units='V',
            format='%.2e',
            type=types.FloatType,
            doc='''Compliance level of the actual source mode.''')
        self.add_parameter('output', flags=Instrument.FLAG_GETSET,
            type=types.IntType,
            format_map={1:'on', 0:'off'})
        self.add_parameter('nplc',
            flags=Instrument.FLAG_GETSET,
            units='#', type=types.FloatType, minval=0.01, maxval=10)
#        self.add_parameter('display', flags=Instrument.FLAG_GETSET, type=types.BooleanType)
        self.add_parameter('averaging_mode', flags=Instrument.FLAG_GETSET,
            type=types.IntType,
            format_map={0:'None', 1:'Moving', 2:'Repeat'},
            doc='''Filter type.''')
        self.add_parameter('averaging_count',
            flags=Instrument.FLAG_GETSET,
            units='#', type=types.IntType, minval=1, maxval=100)
        self.add_parameter('source_range', flags=Instrument.FLAG_GETSET,
            type=types.FloatType,
            format='%.2e',
            units='V',
            doc='''Range of the actual source mode.''')
        self.add_parameter('compliance_tripped', flags=Instrument.FLAG_GET,
            type=types.BooleanType,
            doc='''Indicates whether Keithley is in compliance.''')    
        self.add_parameter('source_rate', flags=Instrument.FLAG_GETSET,
            type = types.FloatType,
            units = 'V/s',
            format = '%.2e',
            doc = '''Sweep rate of the source parameter.''',
            minval=1e-9, maxval=10)

        self.set_parameter_rate('source_value', 5e-5, 50)
        
        self._visainstrument.write('SENS:FUNC:CONC 0')
        
        # Enable single value measurements
        #self.single_measurement()
        
        # Add functions to wrapper
        self.add_function('reset')
        self.add_function('get_all')
        self.add_function('set_defaults')
        self.add_function('send_trigger')
        self.add_function('fetch')
        
        if reset:
            self.reset()
        else:
            # self.set_defaults()
            self.get_all()
        
    # --------------------------------------
    #           functions
    # --------------------------------------
        
    def reset(self):
        '''
        Resets instrument to default values

        Input:
            None
        Output:
            None
        '''
        logging.debug('Resetting instrument')
        self._visainstrument.write('*RST')
        self.get_all()
        
    def set_defaults(self):
        '''
        Set to driver defaults:
        Output=data only
        Mode=Volt:DC
        Digits=7
        Range=10 V
        NPLC=1
        Averaging=off
        '''
        
#        self._visainstrument.write('SYST:PRES')
#        self._visainstrument.write(':FORM:ELEM READ')
            # Sets the format to only the read out, all options are:
            # READing = DMM reading, UNITs = Units,
            # TSTamp = Timestamp, RNUMber = Reading number,
            # CHANnel = Channel number, LIMits = Limits reading

        self.set_source_mode('VOLT')
        self.set_digits(7)
#        self.set_range(10)
        self.set_nplc(10)
        self.set_averaging_mode(0)

    def get_all(self):
        '''
        Reads all relevant parameters from instrument
        Input:
            None
        Output:
            None
        '''
        logging.info('Get all relevant data from device')
        self.get_source_mode()
        outp = self.get_output()
        # self.get_digits()
        self.get_nplc()
        # self.get_display()
#        self.get_autozero()
        self.get_averaging_mode()
        self.get_averaging_count()
        self.get_source_value()
        if outp == 1:
            self.get_sense_value()
            self.get_sense_range()
            self.get_sense_mode()
        self.get_autorange()
        self.get_source_range()
        self.get_source_compliance()
        self.get_compliance_tripped()
        self.get_source_rate()
        
    def send_trigger(self):
        '''
        Send trigger to Keithley, use when triggering is not continous.
        '''
        logging.debug('Sending trigger')
        self._visainstrument.write('INIT')
        self._trigger_sent = True
        
    def fetch(self):
        '''
        Get data at this instance, not recommended, use get_readval.
        Use send_trigger() to trigger the device.
        Note that Readval is not updated since this triggers itself.
        '''

        if self._trigger_sent:
            logging.debug('Fetching data')
            reply = self._visainstrument.ask('FETCH?')
            reply = reply.split(',')
            self._trigger_sent = False
            return reply
        else:
            logging.warning('No trigger sent, use send_trigger')
                    
    def reset_trigger(self):
        '''
        Reset trigger status

        Input:
            None

        Output:
            None
        '''
        logging.debug('Resetting trigger')
        self._visainstrument.write(':ABOR')
    
    def single_measurement(self):
        '''
        Set keithley to perform a single measurements
        '''
        self._visainstrument.write('TRAC:FEED SENS')
        self._visainstrument.write('TRAC:POIN 1')
        self._visainstrument.write('TRAC:FEED:CONT NEVER')
        self._visainstrument.write(':ARM:COUN 1')
        self._visainstrument.write(':TRIG:COUN 1')
        self._visainstrument.write('SOUR:CLE:AUTO OFF')
        self._visainstrument.write('SENS:FUNC:CONC OFF')

    def _fast_sense_mode(self):
        ans = self._visainstrument.ask('SENS:FUNC?')
        try:
            mode = ans.split(':')[0]
            mode = mode.strip('"')
        except:
            mode = ans
        smode = self._key_with_value(self.get_parameter_options('sense_mode')['format_map'], mode)
        return smode
    
    def _fast_source_mode(self):
        ans = self._visainstrument.ask('SOUR:FUNC?')       
        mode = self._key_with_value(self.get_parameter_options('source_mode')['format_map'], ans)
        return mode
        
    def ask(self, string):
        return self._visainstrument.ask(string)
        
# --------------------------------------
#           parameters
# --------------------------------------
    def do_get_sense_value(self, mode=0):
        '''
        Waits for the next value available and returns it as a float.
        Note that if the reading is triggered manually, a trigger must
        be send first to avoid a time-out.

        Input:
            mode : what measurement to perform?

        Output:
            value(float) : last triggerd value on input
        '''
        if self.get_output() == 0:
            print '%s: Not permitted with output off.' % self.get_name()
            return None
        mode=self._fast_sense_mode()
        try:
            reply = self._visainstrument.ask('READ?')
            reply=reply.split(',')   
            return float(reply[mode])
        except:
            return 0.0
        

    def do_get_output(self):
        logging.debug('Get output state')
        ans = self._visainstrument.ask('OUTP?')
        return ans

    def do_set_output(self, val):
        logging.debug('Set output state')
        self._visainstrument.write('OUTP %s' % val)
        self.get_all()

    def do_get_source_value(self):
        '''
        Waits for the next value available and returns it as a float.
        Note that if the reading is triggered manually, a trigger must
        be send first to avoid a time-out.

        Input:
            None

        Output:
            value(float) : last triggerd value on input
        '''
        logging.debug('Read source value')
        
        mode = self._fast_source_mode()
        modstr = self.get_parameter_options('source_mode')['format_map'][mode]
        
        return float(self._visainstrument.ask('SOUR:%s:LEV:AMPL?' % modstr))

    def do_set_source_value(self, val, mode=None):
        '''
        Waits for the next value available and returns it as a float.
        Note that if the reading is triggered manually, a trigger must
        be send first to avoid a time-out.

        Input:
            None

        Output:
            value(float) : last triggerd value on input
        '''
        logging.debug('Set source value')
        
        mode = self._fast_source_mode()
        modstr = self.get_parameter_options('source_mode')['format_map'][mode]
        
        self._visainstrument.write('SOUR:%s:LEV:AMPL %6.12f' % (modstr, val))
        if self.get_compliance_tripped():
            return None
        else:
            return True
        
    def do_set_sense_range(self, val):
        '''
        Set range to the specified value 

        Input:
            val (float)   : Range in specified units

        Output:
            None
        '''
        if self.get_output() == 0:
            print '%s: Not permitted with output off.' % self.get_name()
            return False
        logging.debug('Set range to %s' % val)
        mode = self._fast_sense_mode()
        modstr = self.get_parameter_options('sense_mode')['format_map'][mode]
        self._visainstrument.write('SENS:%s:RANG:UPP %d' % (modstr, val))
        
    def do_get_sense_range(self):
        '''
        Get range for the specified mode.

        Output:
            range (float) : Range in the specified units
        '''
        if self.get_output() == 0:
            print '%s: Not permitted with output off.' % self.get_name()
            return None
        logging.debug('Get range')
        mode = self._fast_sense_mode()
        modstr = self.get_parameter_options('sense_mode')['format_map'][mode]
        ans = self._visainstrument.ask('SENS:%s:RANG:UPP?' % modstr)
        return float(ans)

    def do_get_source_compliance(self):
        mode = self._fast_source_mode()
        modstr = self.get_parameter_options('source_mode')['format_map'][not mode]
        ans = self._visainstrument.ask('SENS:%s:PROT:LEV?' % modstr)
        return float(ans)
        
    def do_set_source_compliance(self, val):
        mode = self._fast_source_mode()
        modstr = self.get_parameter_options('source_mode')['format_map'][not mode]
        self._visainstrument.write('SENS:%s:PROT:LEV %6.10f' % (modstr, val))
        
    def do_set_digits(self, val):
        '''
        Set the display resolution to the specified value
        Input:
            val (int)     : Number of digits

        Output:
            None
        '''
        logging.debug('Set display resolution to %s' % val)
        self._visainstrument.write('DISP:DIG %s' % (val))

    def do_get_digits(self):
        '''
        Get the display resolution
        Input:

        Output:
            resolution (float)
        '''
        logging.debug('Getting display resolution')
        return self._visainstrument.ask('DISP:DIG?')

    def do_set_nplc(self, val):
        '''
        Set integration time to the specified value in Number of Powerline Cycles.
        To set the integrationtime in seconds, use set_integrationtime().
        Note that this will automatically update integrationtime as well.
        If mode=None the current mode is assumed

        Input:
            val (float)   : Integration time in nplc.

        Output:
            None
        '''
        logging.debug('Set integration time to %s PLC' % val)
        mode = self._fast_sense_mode()
        modstr = self.get_parameter_options('sense_mode')['format_map'][mode]
        command = str(val)
        if self.get_output()==1:
            self._visainstrument.write(':SENS:%s:NPLC %s' % (modstr, command))
        else:
            logging.debug('Accessing NPLC settings not permitted with output off!')

        
    def do_get_nplc(self):
        '''
        Get integration time in Number of PowerLine Cycles.
        To get the integrationtime in seconds, use get_integrationtime().
        If mode=None the current mode is assumed

        Input:
            none

        Output:
            time (float) : Integration time in PLCs
        '''
        logging.debug('Read integration time in PLCs')
        mode = self._fast_sense_mode()
        modstr = self.get_parameter_options('sense_mode')['format_map'][mode]
        if self.get_output() ==1:
            ans = self._visainstrument.ask(':SENS:%s:NPLC?' % modstr)
        else:
            logging.debug('Accessing NPLC settings not permitted with output off!')
            ans = 1.0
        return float(ans)

    def do_set_source_mode(self, mode):
        '''
        Set the source mode to the specified value

        Input:
            mode (int) : mode to be set:
                            0: VOLTage source
                            1: CURRent source
            
        Output:
            None
        '''

        logging.debug('Set source mode to %s', mode)
        unit = {0:'V',1:'A'}
        
        if mode == 1:
            modstr = 'CURR'
            minval=-210
            maxval=210
        elif mode == 0:
            modstr = 'VOLT'
            minval=-1.05
            maxval=1.05
        else:
            logging.error('invalid source mode %s' % mode)
        
        self.set_parameter_options('source_value', units=unit[mode])
        self.set_parameter_options('source_range', units=unit[mode])
        self.set_parameter_options('source_compliance', minval=minval, maxval=maxval, units=unit[not mode])
        self.set_parameter_options('source_rate', units='%s/s' % unit[mode])
        self._visainstrument.write('SOUR:FUNC %s' % modstr)
        
        self.get_source_range()
        self.get_output()

    def do_get_source_mode(self):
        '''
        Read the mode from the device
        Input:
            None
      Output:
            mode (string) : Current mode
        '''
        string = 'SOUR:FUNC?'
        logging.debug('Getting source mode')
        ans = self._visainstrument.ask(string)
        mode = self._key_with_value(self.get_parameter_options('source_mode')['format_map'], ans)
        
        unit = {0:'V',1:'A'}
        self.set_parameter_options('source_value', units=unit[mode])
        self.set_parameter_options('source_range', units=unit[mode])
        self.set_parameter_options('source_rate', units='%s/s' % unit[mode])
        self.set_parameter_options('source_compliance', units=unit[not mode])
        
        return mode

    def do_set_sense_mode(self, mode):
        '''
        Set the sense mode to the specified value
        Input:
            mode (int) : mode to be set.
        Output:
            None
        '''
        if self.get_output() == 0:
            print '%s: Not permitted with output off.' % self.get_name()
            return None        
        logging.debug('Set sense mode to %s', mode)
        
        modstr = self.get_parameter_options('sense_mode')['format_map'][mode]
        command = 'SENS:FUNC "%s"' % modstr
        
        self._visainstrument.write(command)
        unit={0:'V',1:'A',2:'Ohm'}
        self.set_parameter_options('sense_value',units=unit[mode])
        self.set_parameter_options('sense_range',units=unit[mode])
        self.get_sense_range()

    def do_get_sense_mode(self):
        '''
        Read the mode from the device

        Input:
            None

        Output:
            mode (string) : Current mode
        '''
        if self.get_output() == 0:
            print '%s: Not permitted with output off.' % self.get_name()
            return None
        logging.debug('Getting sense mode')
        
        ans = self._visainstrument.ask('SENS:FUNC?')
        ans = ans.strip('"')
        try:
            ans = ans.split(':')[0]
        except:
            pass
        mode = self._key_with_value(self.get_parameter_options('sense_mode')['format_map'], ans)       
        unit={0:'V',1:'A',2:'Ohm'}
        self.set_parameter_options('sense_value',units=unit[mode])
        self.set_parameter_options('sense_range',units=unit[mode])
        return mode

    def do_get_display(self):
        '''
        Read the staturs of diplay

        Input:
            None

        Output:
            True = On
            False= Off
        '''
        logging.debug('Reading display from instrument')
        reply = self._visainstrument.ask('DISP:ENAB?')
        return bool(int(reply))

    def do_set_display(self, val):
        '''
        Switch the diplay on or off.

        Input:
            val (boolean) : True for display on and False for display off

        Output

        '''
        logging.debug('Set display to %s' % val)
        val = bool_to_str(val)
        return self._visainstrument.write('DISP:ENAB %s' % val)

    def do_set_averaging_mode(self, val):
        '''
        Switch averaging on or off.
        If mode=None the current mode is assumed

        Input:
            val (boolean)

        Output:
            None
        '''
        logging.debug('Set averaging to %s ' % val)
        if val==0:
            self._visainstrument.write('SENS:AVER:STAT 0')
        elif val==1:
            self._visainstrument.write('SENS:AVER:STAT 1')
            self._visainstrument.write('SENS:AVER:TCON MOV')
        elif val==2:
            self._visainstrument.write('SENS:AVER:STAT 1')
            self._visainstrument.write('SENS:AVER:TCON REP')

    def do_get_averaging_mode(self):
        '''
        Get status of averaging.

        Output:
            result (boolean)
        '''
        logging.debug('Get averaging')
        reply = self._visainstrument.ask('SENS:AVER:STAT?')
        try:
            status = int(reply)
        except:
            pass
        if status == 1 or status == 'ON':
            type = self._visainstrument.ask('SENS:AVER:TCON?')
            if type == 'MOV':
                return 1
            elif type == 'REP':
                return 2
        else:
            return 0

    def do_set_averaging_count(self, val):
        '''
        Set averaging count.

        Input:
            val (int)   : Averaging count.

        Output:
            None
        '''
        logging.debug('Set averaging_count to %s ' % val)
        self._visainstrument.write('SENS:AVER:COUN %d' % val)

    def do_get_averaging_count(self):
        '''
        Get averaging count.

        Input:
            None
            
        Output:
            result (int) : Averaging count
        '''
        logging.debug('Get averaging count')
        reply = self._visainstrument.ask('SENS:AVER:COUN?')
        return int(float(reply))
        
    def do_set_autorange(self, val):
        '''
        Switch autorange on or off.

        Input:
            val (int or string) 1 or on, 0 or off

        Output:
            None
        '''
        logging.debug('Set autorange to %s ' % val)
        mode = self._fast_sense_mode()
        modstr=self.get_parameter_options('sense_mode')['format_map'][mode]
        
        self._visainstrument.write(':SENS:%s:RANG:AUTO %i' % (modstr,val))
        return True
        
    def do_get_autorange(self):
        '''
        Get status of averaging.

        Output:
            result (boolean)
        '''
        logging.debug('Get autorange')
        mode = self._fast_sense_mode()
        modstr=self.get_parameter_options('sense_mode')['format_map'][mode]
        
        reply = self._visainstrument.ask(':SENS:%s:RANG:AUTO?' % modstr)
        return int(reply)

    def do_get_source_range(self):
        mode = self._fast_source_mode()
        modstr = self.get_parameter_options('source_mode')['format_map'][mode]
        reply = self._visainstrument.ask(':SOUR:%s:RANG?' % modstr)
        return float(reply)
        
    def do_set_source_range(self, value):
        mode = self._fast_source_mode()
        modstr = self.get_parameter_options('source_mode')['format_map'][mode]
        self._visainstrument.write('SOUR:%s:RANG %.6e' % (modstr, value))
        return True

    def do_get_compliance_tripped(self):
        mode = self._fast_source_mode()
        modstr = self.get_parameter_options('source_mode')['format_map'][not mode]
        ans = self._visainstrument.ask('SENS:%s:PROT:TRIP?' % modstr)
        return int(ans)
    
    def do_set_source_rate(self, val):
        dt = self.get_parameter_options('source_value')['stepdelay']
        rampstep = val*dt*1e-3
        self.set_parameter_rate('source_value', rampstep, dt)
        
    def do_get_source_rate(self):
        rs = self.get_parameter_options('source_value')['maxstep']
        dt = self.get_parameter_options('source_value')['stepdelay']*1e-3
        return rs/dt 
    
    # -----------------------------------------------------------
    # Autozero settings, not used in current driver version.
    # -----------------------------------------------------------              
        
    def do_get_autozero(self):
        '''
        Read the staturs of the autozero function

        Input:
            None

        Output:
            reply (boolean) : Autozero status.
        '''
        logging.debug('Reading autozero status from instrument')
        reply = self._visainstrument.ask(':ZERO:AUTO?')
        return bool(int(reply))

    def do_set_autozero(self, val):
        '''
        Switch the diplay on or off.

        Input:
            val (boolean) : True for display on and False for display off

        Output

        '''
        logging.debug('Set autozero to %s' % val)
        val = bool_to_str(val)
        return self._visainstrument.write('SENS:ZERO:AUTO %s' % val)   

        
    # -----------------------------------------------------------
    # Old trigger settings, not used in current driver version.
    # -----------------------------------------------------------        
    def do_set_trigger_count(self, val):
        '''
        Set trigger count
        if val>9999 count is set to INF

        Input:
            val (int) : trigger count

        Output:
            None
        '''
        logging.debug('Set trigger count to %s' % val)
        if val > 9999:
            val = 'INF'
        self._set_func_par_value('TRIG', 'COUN', val)

    def do_get_trigger_count(self):
        '''
        Get trigger count

        Input:
            None

        Output:
            count (int) : Trigger count
        '''
        logging.debug('Read trigger count from instrument')
        ans = self._get_func_par('TRIG', 'COUN')
        try:
            ret = int(ans)
        except:
            ret = 0

        return ret

    def do_set_trigger_delay(self, val):
        '''
        Set trigger delay to the specified value

        Input:
            val (float) : Trigger delay in seconds or -1 for auto

        Output:
            None
        '''
        if val == -1:
            logging.debug('Set trigger delay to auto')
            self._set_func_par_value('TRIG', 'DEL:AUTO', 'OFF')
        else:
            logging.debug('Set trigger delay to %s sec', val)
            self._set_func_par_value('TRIG', 'DEL', '%s' % val)

    def do_get_trigger_delay(self):
        '''
        Read trigger delay from instrument

        Input:
            None

        Output:
            delay (float) : Delay in seconds, or -1 for auto
        '''
        logging.debug('Read trigger delay from instrument')
        val = self._get_func_par('TRIG', 'DEL:AUTO')
        if val == '1':
            return -1
        else:
            return self._get_func_par('TRIG', 'DEL')

    def do_set_trigger_source(self, val):
        '''
        Set trigger source

        Input:
            val (string) : Trigger source

        Output:
            None
        '''
        logging.debug('Set Trigger source to %s' % val)
        self._set_func_par_value('TRIG', 'SOUR', val)

    def do_get_trigger_source(self):
        '''
        Read trigger source from instrument

        Input:
            None

        Output:
            source (string) : The trigger source
        '''
        logging.debug('Getting trigger source')
        return self._get_func_par('TRIG', 'SOUR')
        
        
# --------------------------------------
#           Internal Routines
# --------------------------------------

    def _key_with_value(self, dict, value):
        ''' 
        Function to quickly get the keys from dictionary
        values.
        Input:
            dict (dictionary)   : dict to search
            value (value)       : value to look for key
       
        Output:
            v (key)             : key belonging to value 
    
        '''
        for k, v in dict.iteritems():
            if v == value:
                return k
        return None