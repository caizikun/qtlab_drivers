# Lakeshore 350, Lakeshore 350 temperature controller driver
#  Original driver for Lakeshore 340 by:
#  Reinier Heeres <reinier@heeres.eu>, 2010
#
#  Modified by Ludo Cornelissen for Lakeshore 350
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
import re
import math
import time
import qt
import numpy as np
import sys
import os
import matplotlib.pyplot as plt
import pylab
import matplotlib as mpl

class Lakeshore_350(Instrument):

    def __init__(self, name, address, reset=False):
        Instrument.__init__(self, name)

        self._address = address
        self._visa = visa.instrument(self._address)
        self._channels = ('A', 'B')
        self._outputs = ('1', '2')

        self.add_parameter('temperature',
            flags=Instrument.FLAG_GET,
            type=types.FloatType,
            channels=self._channels,
            units='K')

        self.add_parameter('sensor_resistance',
            flags=Instrument.FLAG_GET,
            type=types.FloatType,
            channels=self._channels,
            units='Ohm')

        self.add_parameter('heater_range',
            flags=Instrument.FLAG_GETSET,
            type=types.IntType,
            format_map={
                0: 'off',
                1: '10 mA',
                2: '33 mA',
                3: '100 mA',
                4: '330 mA',
                5: '1 A',
                },
            channels = self._outputs)

        self.add_parameter('heater_output',
            flags=Instrument.FLAG_GET,
            type=types.FloatType,
            units='%',
            channels = self._outputs)

        self.add_parameter('mode',
            flags=Instrument.FLAG_GETSET,
            type=types.IntType,
            format_map={0: 'Local', 1: 'Remote', 2: 'Remote, local lock'})

        self.add_parameter('pid',
            flags=Instrument.FLAG_GETSET,
            type=types.ListType,
            channels=self._outputs)

        self.add_parameter('setpoint',
            flags=Instrument.FLAG_GETSET,
            type=types.FloatType,
            channels=self._outputs,
            units='K')

        self.add_function('local')
        self.add_function('remote')
        self.add_function('ramp_temperature')

        if reset:
            self.reset()
        else:
            self.get_all()

    # ------------------------------------------------------
    # ------------------- Functions ------------------------
    # ------------------------------------------------------
            
    def reset(self):
        self._visa.write('*RST')

    def get_all(self):
        paramlist = self.get_parameter_names()
        for parameter in paramlist:
            command = 'self.get_' + parameter + '()'
            eval(command)
        
    def ramp_temperature(self, value, precision=0.015, timestep=20.0, timeout=1800):
        '''
        Ramps the temperature of the crysostat to a designated value and waits
        untill the sensor temperature stabilizes. Minimum waiting time is 
        (timestep)*15 seconds.
        
        The temperature setpoint is sent to the ITC503, after which qtlab goes
        into wait mode. Every (timestep) seconds, the measured temperature is 
        checked and compared to the setpoint. The temperature is considered stable
        when the mean error is smaller than (precision) over a period of 
        (timestep)*15 seconds.
        
        Shorter timestep will result in shorter waiting times, however the
        temperature might not be fully stabilized then.
        
        Input:
            value (float)                   :   Temperature to ramp to (Kelvin)
            precision (float)               :   Mean temperature error allowed 
                                                over a time period of timestep*15
                                                seconds. Default is 15mK.
            timestep (float)                :   time between each step in evaluating
                                                the error while waiting. Default
                                                is 20s, and taking 15 steps.
            timeout (float)                 :   Maximum waiting time for the temperature
                                                ramp. If waiting longer than <timeout>
                                                seconds, the script will resume and the ramp
                                                is regarded as completed.
                                                
        Output:
            None
        '''
        output = '1'
        channel = 'A'
        name = self.get_name()
        if self.get_heater_range1() == 0:
            print '%s: Unable to perform ramp, heater_range1 is set to "off"!' % name
            ans = raw_input('%s: Please select a heater range to set (1 to 5).' % name)
            try: 
                ans = int(ans)
            except:
                print '%s: Invalid range, aborting ramp.' % name
                return False
            if ans in [1, 2, 3, 4, 5]:
                self.set_heater_range1(ans)
                print '%s: heater_range1 set to %i' % (name, ans)
            else:
                print '%s: Invalid range, aborting ramp.' % name
                return False
                
        self.set_setpoint1(value)
        print '%s: Ramp to %.2fK.' % (name, value)
        tstart = time.time()
        number_of_points = 15
        errors = []
        temperatures = [self.get_temperatureA()]
        times = [0]
        heaters = [self.get_heater_output1()]
        qt.msleep(timestep)
        
        for i in np.arange(0,number_of_points):
            T = self.get_temperatureA()
            errors.append( np.abs(value - T) )
            temperatures.append(T)
            heaters.append(self.get_heater_output1())
            times.append(time.time()-tstart)
            qt.msleep(timestep)
            
        msg1 = 'stabilized at'
        msg2 = ' after %d seconds.' % int(time.time()-tstart)
        timeout_achieved = False
        
        while np.mean(errors[-number_of_points:]) > precision and not timeout_achieved:
            T = self.get_temperatureA()
            error = np.abs(value - T)
            heaters.append(self.get_heater_output1())
            temperatures.append(T)
            errors.append(error)
            times.append(time.time()-tstart)
            meanerror = np.mean(errors[-number_of_points:])
            
            print '%s: Awaiting stable Temp. Mean error: %3.3fK. Required: %1.2fK.\r' % (name, meanerror, precision) ,
            sys.stdout.flush()
            qt.msleep(timestep)
            msg1 = 'stabilized at'
            msg2 = ' after %d seconds.' % int(time.time()-tstart)
            
            if time.time() > (tstart+timeout):
                timeout_achieved = True
                print '\n%s: Ramping for %.1f seconds total. Maximum waiting time achieved. Script operation resumed.' % (name, int(time.time()-tstart))
                msg1 = 'after ramp at'
                msg2 = ', current error %.3fK.' % error
        self.get_all()
        print '\n%s: Sensor temperature %s %2.2fK%s' % (name, msg1, self.get_temperatureA(), msg2)
        
        plot = True
        if plot:
            plotname = 'temperature_ramp_'+ time.strftime('%Y%m%d_%H:%M:%S', time.localtime(tstart))
            fig = plt.figure()
            ax = fig.add_subplot(111)
            T = ax.plot(times, temperatures,'r', label='Temperature')
            ax.set_xlabel('Time (seconds)', fontsize=16)
            ax.set_ylabel('Temperature (Kelvin)', fontsize=16)
            ax.set_title(plotname)
            y_formatter = mpl.ticker.ScalarFormatter(useOffset=False)
            ax.yaxis.set_major_formatter(y_formatter)
            ax2 = ax.twinx()
            H = ax2.plot(times, heaters, 'k', label='Heater out')
            ax2.set_ylabel('Heater output (%)', fontsize=16)
            ax.tick_params(axis='y', colors='red')
            ax.yaxis.label.set_color('red')
            filename = os.path.abspath(qt.config['datadir'])+'\\'+'temperature_ramp_'+ time.strftime('%Y%m%d_%H%M%S', time.localtime(tstart))+'.png'
            pylab.savefig(filename,bbox_inches='tight')
            fig.clear()
            
    # ------------------------------------------------------
    # ------------ Get and Set parameters ------------------
    # ------------------------------------------------------
        
    def do_get_temperature(self, channel):
        ans = self._visa.ask('KRDG? %s' % channel)
        return float(ans)
        
    def do_get_sensor_resistance(self, channel):
        ans = self._visa.ask('SRDG? %s' % channel)
        return float(ans)
        
    def do_get_heater_range(self, channel):
        ans = self._visa.ask('RANGE? %s' % channel)
        return ans
        
    def do_set_heater_range(self, val, channel):
        # First turn heater on
        self._visa.write('OUTMODE %s, 1, %s, 0' % (channel, channel) )
        # Then set range to correct value
        self._visa.write('RANGE %s,%d' % (channel, val))
        
    def do_get_heater_output(self, channel):
        ans = self._visa.ask('HTR? %s' % channel)
        return ans
        
    def do_get_mode(self):
        ans = self._visa.ask('MODE?')
        return int(ans)

    def do_set_mode(self, mode):
        self._visa.write('MODE %d' % mode)

    def local(self):
        self.set_mode(1)

    def remote(self):
        self.set_mode(2)

    def do_get_pid(self, channel):
        ans = self._visa.ask('PID? %s' % channel)
        fields = ans.split(',')
        if len(fields) != 3:
            return None
        fields = [float(f) for f in fields]
        return fields
        
    def do_set_pid(self, val, channel):
        print '%s: Setting pid values not implemented.' % self.get_name()
        return False
        
    def do_get_setpoint(self, channel):
        ans = self._visa.ask('SETP? %s' % channel)
        return float(ans)
        
    def do_set_setpoint(self, val, channel):
        self._visa.write('SETP %s,%f' % (channel,val))
        