#!/usr/bin/env python3
#
# Copyright (C) 2018  Maurice van der Pot <griffon26@kfk4ever.com>
#
# This file is part of taserver
# 
# taserver is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
# 
# taserver is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
# 
# You should have received a copy of the GNU Affero General Public License
# along with taserver.  If not, see <http://www.gnu.org/licenses/>.
#

from bitarray import bitarray
import string
import struct
import sys
import time
import traceback

class ParseError(Exception):
    pass

def toint(bits):
    zerobytes = bytes( (0,0,0,0) )
    longbytes = (bits.tobytes() + zerobytes)[0:4]
    return struct.unpack('<L', longbytes)[0]

def getnbits(n, bits):
    if n > len(bits):
        raise EOFError
    return bits[0:n], bits[n:]

def getstring(bits):
    stringbytes = bits.tobytes()
    result = []
    for b in stringbytes:
        if b != 0:
            result.append(chr(b))
        else:
            break

    return ''.join(result), bits[(len(result) + 1) * 8:]

class PacketWriter():
    def __init__(self, outfile):
        self.offset = 0
        self.outfile = outfile
        self.indentlevels = []

    def _writeindentedline(self, something):
        self.outfile.write(self.offset * ' ' + something + '\n')

    def writefield(self, bits, description):
        if bits:
            self._writeindentedline('%s %s' % (bits.to01(), description))
            self.offset += len(bits)
        else:
            self._writeindentedline('x %s' % description)
            self.offset += 1
        self.indentlevels.append(self.offset)

    def writerest(self, message, bits):
        self.offset = 0
        self.indentlevels = []
        if len(bits) > 0:
            self._writeindentedline(message + ': ' + bits.to01() + '\n')

    def writeline(self, line):
        if self.offset != 0:
            raise RuntimeError('Cannot write line in the middle of another')
        self.outfile.write(line + '\n')


    def getindentlevel(self):
        return len(self.indentlevels)

    def restoreindentlevel(self, level):
        if level >= len(self.indentlevels):
            raise RuntimeError('Cannot restore indent to a deeper level (at %d, requested %d)' % (len(self.indentlevels), level))
        self.indentlevels = self.indentlevels[:level]
        self.offset = self.indentlevels[-1]

    def exdent(self, count):
        self.indentlevels = self.indentlevels[:-count]
        self.offset = self.indentlevels[-1]

def findshiftedstrings(bindata, i):
    emptychar = ' '
    continuationchar = '.'
    shiftedbytes = bindata[i:].tobytes()
    linechars = []
    stringchars = []
    for b in shiftedbytes:
        if b == 0:
            if len(stringchars) > 3:
                linechars.extend(stringchars + [continuationchar] * ((len(stringchars) + 1) * 7 + 1))
                stringchars = []
            else:
                linechars.extend([emptychar] * (len(stringchars) + 1) * 8)
                stringchars = []
            
        elif chr(b) in string.ascii_letters + string.digits + string.punctuation + ' ':
            stringchars.append(chr(b))
            
        else:
            linechars.extend([emptychar] * len(stringchars) * 8)
            stringchars = []
            linechars.extend([emptychar] * 8)

    if len(stringchars) > 3:
        linechars.extend(stringchars + [continuationchar] * ((len(stringchars) + 1) * 7 + 1))
    else:
        linechars.extend([emptychar] * (len(stringchars) + 1) * 8)

    result = ''.join(linechars)
    if result.strip() == '':
        return None
    else:
        return result

def binfile2packetbits(infile):
    for linenr, line in enumerate(infile.readlines()):

        line = line.strip()

        if not line:
            continue

        packetsizestr, bindatastr = line.split()

        packetsize = int(packetsizestr)
        bindata = bitarray(bindatastr, endian='little')

        if packetsize != len(bindata) / 8:
            raise RuntimeError('Packet size does not match number of bits on line %d' % (linenr + 1))

        yield bindata
    

class Parser():
    def __init__(self, packetwriter):
        self.packetwriter = packetwriter
        self.channels = {}
        self.classdict = {
            '00110100101111010100000000000000' : 'TrFlagCTF_DiamondSword',
            '00100111010010011000000000000000' : 'UTTeamInfo',
            '00100100101111010100000000000000' : 'TrFlagCTF_BloodEagle',
            '00000110101111001100000000000000' : 'TrPlayerReplicationInfo',
            '00110001010000010100000000000000' : 'TrPlayerController',
            '01110001101110110100000000000000' : 'TrGameReplicationInfo',
            '00000101100101011110000000000000' : 'WorldInfo',
            '00010011100001101100000000000000' : 'TrServerSettingsInfo',
            '00111100001100100100000000000000' : 'TrBaseTurret_DiamondSword',
            '01001010100010101100000000000000' : 'TrRadarStation_DiamondSword',
            '00110111000101011110000000000000' : 'TrCTFBase_DiamondSword',
            '01100110100101011110000000000000' : 'TrVehicleStation_DiamondSword',
            '01001011110100001100000000000000' : 'TrInventoryStationCollision',
            '00000000110010101100000000000000' : 'TrRepairStationCollision',
            '00111010100001100100000000000000' : 'TrPlayerPawn',
            '01111100101110010100000000000000' : 'TrDevice_LightSpinfusor',
            '01101100101110010100000000000000' : 'TrDevice_LightAssaultRifle',
            '01100101110110010100000000000000' : 'TrDevice_GrenadeLauncher_Light',
            '01001000101110010100000000000000' : 'TrDevice_LaserTargeter',
            '01111000100110010100000000000000' : 'TrDevice_Blink',
            '01000011100110010100000000000000' : 'TrDevice_ConcussionGrenade',
            '00100111101110010100000000000000' : 'TrDevice_Melee_DS',
            '01101101010100001100000000000000' : 'TrInventoryManager',
            '00000011110100001100000000000000' : 'TrStationCollision',
            '00011100001100100100000000000000' : 'TrBaseTurret_BloodEagle',
            '01110010100010101100000000000000' : 'TrRadarStation_BloodEagle',
            '00100110100101011110000000000000' : 'TrVehicleStation_BloodEagle',
            '00111100100101011110000000000000' : 'TrPowerGenerator_BloodEagle',
            '01010111000101011110000000000000' : 'TrCTFBase_BloodEagle',
            
        }
        self.propertydict = {
            '1110110' : ('Team (9 bits)', 9),
            '1111101' : ('Team (10 bits)', 10)
        }
        self.instancedict = {}

    def _parsepayload(self, bindata, payloadsize, channel):
        
        payloadbits, bindata = getnbits(payloadsize, bindata)
        
        channelisnew = channel not in self.channels

        if channelisnew:
            try:
                classbits, payloadbits = getnbits(32, payloadbits)
                classkey = classbits.to01()
                if classkey not in self.classdict:
                    classname = 'unknown%d' % len(self.classdict)
                    self.classdict[classkey] = classname
                classname = self.classdict[classkey]

                self.instancedict[classname] = self.instancedict.get(classname, -1) + 1
                self.channels[channel] = '%s_%d' % (classname, self.instancedict[classname])
                self.packetwriter.writefield(classbits, '(new object %s)' % self.channels[channel])
                
                if(len(payloadbits) > 0):
                    self.packetwriter.writefield(payloadbits, '(rest of payload)')

            except:
                self.packetwriter.writefield(payloadbits, 'ERROR: exception during parsing of payload')
        else:
            self.packetwriter.writefield(bitarray(), '(object = %s)' % self.channels[channel])

            while payloadbits:
                propertylevel = self.packetwriter.getindentlevel()
                propertyidbits, payloadbits = getnbits(7, payloadbits)
                propertykey = propertyidbits.to01()
                propertyname, propertylength = self.propertydict.get(propertykey, ('Unknown', None))

                self.packetwriter.writefield(propertyidbits, '(property = %s)' % propertyname)
                if propertylength:
                    propertyvaluebits, payloadbits = getnbits(propertylength, payloadbits)
                    self.packetwriter.writefield(propertyvaluebits, '(value)')
                else:
                    self.packetwriter.writefield(payloadbits, '(rest of payload)')
                    break

                self.packetwriter.restoreindentlevel(propertylevel)

        return bindata

    def _parsechannel(self, bindata, withcounter, flag1level):
        channelbits, bindata = getnbits(10, bindata)
        channel = toint(channelbits)
        self.packetwriter.writefield(channelbits, '(channel = %d)' % channel)

        if withcounter:
            counterbits, bindata = getnbits(5, bindata)
            counter = toint(counterbits)
            self.packetwriter.writefield(counterbits, '(counter = %d)' % counter)

            unknownbits, bindata = getnbits(8, bindata)
            self.packetwriter.writefield(unknownbits, '')

        payloadsizebits, bindata = getnbits(14, bindata)
        payloadsize = toint(payloadsizebits)
        self.packetwriter.writefield(payloadsizebits, '(payloadsize = %d)' % payloadsize)

        bindata = self._parsepayload(bindata, payloadsize, channel)

        state = 'flag1'
        self.packetwriter.restoreindentlevel(flag1level)

        return bindata, state
        
    def parse(self, bindata):
        originalbindata = bitarray(bindata)

        self.packetwriter.writeline('Packet with size %d' % (len(bindata) / 8))

        shiftedstrings = [findshiftedstrings(bindata, i) for i in range(8)]

        seqnrbits, bindata = getnbits(14, bindata)
        seqnr = toint(seqnrbits)
        self.packetwriter.writefield(seqnrbits, '(seqnr = %d)' % seqnr)

        try:
            state = 'flag1'
            while len(bindata) > 0 and state != 'end':
                if state == 'flag1':
                    flag1level = self.packetwriter.getindentlevel()
                    
                    flag1bits, bindata = getnbits(1, bindata)
                    flag1 = toint(flag1bits)
                    self.packetwriter.writefield(flag1bits, '(flag1 = %d)' % flag1)

                    if flag1:
                        if len(bindata) >= 14:
                            numbits, bindata = getnbits(14, bindata)
                            num = toint(numbits)
                            self.packetwriter.writefield(numbits, '(num = %d)' % num)

                            self.packetwriter.restoreindentlevel(flag1level)
                        else:
                            state = 'end'
                    else:
                        state = 'flag1a'

                elif state == 'flag1a':
                    flag1alevel = self.packetwriter.getindentlevel()
                    
                    flag1abits, bindata = getnbits(2, bindata)
                    flag1a = toint(flag1abits)
                    self.packetwriter.writefield(flag1abits, '(flag1a = %d)' % flag1a)


                    if flag1abits == bitarray('00'): # actor
                        bindata, state = self._parsechannel(bindata, False, flag1level)
                    
                    elif flag1abits == bitarray('01'): # RPC
                        bindata, state = self._parsechannel(bindata, True, flag1level)

                        # TODO: integrate the code below into _parsepayload
                        '''
                        while True:
                            level = self.packetwriter.getindentlevel()
                            
                            part1flags, bindata = getnbits(2, bindata)
                            self.packetwriter.writefield(part1flags, '(part1flags = %s)' % part1flags)

                            if part1flags == bitarray('10'):
                                state = 'end'
                                break
                            elif part1flags == bitarray('11'):
                                part1size = 166
                            elif part1flags == bitarray('00'):
                                part1size = 206
                            else:
                                raise ParseError('Unknown part1flags: %s' % part1flags)


                            part1bits, bindata = getnbits(part1size, bindata)
                            self.packetwriter.writefield(part1bits, '')

                            part1name, bindata = getstring(bindata)
                            self.packetwriter.writefield(None, '(%s)' % part1name)

                            part2flags, _ = getnbits(2, bindata)
                            if part2flags == bitarray('00'):
                                nbits = 128
                            elif part2flags == bitarray('01'):
                                nbits = 144
                            elif part2flags == bitarray('11') or part2flags == bitarray('10'):
                                nbits = 168
                            else:
                                raise ParseError('Unknown part2flags: %s' % part2flags)
                            part2bits, bindata = getnbits(nbits, bindata)
                            self.packetwriter.writefield(part2bits, '')
                            
                            part2name, bindata = getstring(bindata)
                            self.packetwriter.writefield(None, '(%s)' % part2name)

                            self.packetwriter.restoreindentlevel(level)
                        '''
                    elif flag1abits == bitarray('10'):
                        
                        unknownbits, bindata = getnbits(2, bindata)
                        self.packetwriter.writefield(unknownbits, '')

                        bindata, state = self._parsechannel(bindata, True, flag1level)
                        
                    elif flag1abits == bitarray('11'):
                        state = 'flag1a'
                        self.packetwriter.restoreindentlevel(flag1alevel)


                        # TODO: integrate the code below into _parsepayload
                        '''

                        # This is only correct for one instance where
                        # flag1a is 3. TODO: gather other small packets
                        # with flag1a == 3 and see how to make this more
                        # generally applicable
                        
                        unknownbits, bindata = getnbits(2, bindata)
                        self.packetwriter.writefield(unknownbits, '')

                        channelbits, bindata = getnbits(10, bindata)
                        channel = toint(channelbits)
                        self.packetwriter.writefield(channelbits, '(channel = %d)' % channel)

                        state = 'end'
                        '''
                        '''
                        unknownbits, bindata = getnbits(108, bindata)
                        self.packetwriter.writefield(unknownbits, '')
                        
                        playername, bindata = getstring(bindata)
                        self.packetwriter.writefield(None, '(player = %s)' % playername)

                        unknownbits, bindata = getnbits(8, bindata)
                        self.packetwriter.writefield(unknownbits, '')

                        state = 'flag1a'
                        self.packetwriter.restoreindentlevel(flag1alevel)
                        '''

                    else:
                        raise ParseError('Unknown value for flag1a: %s' % flag1a)
                else:
                    raise ParseError('Unknown value for state: %s' % state)

        except UnicodeEncodeError as e:
            self.packetwriter.writerest('ERROR: Failed conversion to unicode (%s)' % str(e), bindata)
        except EOFError:
            self.packetwriter.writerest('ERROR: Attempted to read more bits than what\'s left', bindata)
        except ParseError as e:
            self.packetwriter.writerest('ERROR: Parsing failed (%s). Remaining bits:' % str(e), bindata)
        else:
            # Don't report an error when the only bits left are the last few of the last byte
            if len(bindata) > 7 or toint(bindata) != 0:
                self.packetwriter.writerest('ERROR: Bits left after parsing', bindata)
            else:
                self.packetwriter.writerest('    Bits left over in the last byte', bindata)

        if any(shiftedstrings):
            self.packetwriter.writeline('    String overview:')
            self.packetwriter.writeline('    ' + originalbindata.to01())
            for i, shiftedstring in enumerate(shiftedstrings):
                if shiftedstring:
                    self.packetwriter.writeline('    %s%s (shifted by %d bits)' % (' ' * i, shiftedstring, i))
            self.packetwriter.writeline('')
        

def main(infilename):
    outfilename = infilename + '_parsed.txt'

    with open(infilename, 'rt') as infile:
        with open(outfilename, 'wt') as outfile:
            print('Writing output to %s...' % outfilename)
            
            packetwriter = PacketWriter(outfile)
            parser = Parser(packetwriter)

            for bindata in binfile2packetbits(infile):
                parser.parse(bindata)
                
if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            print('Usage: %s <captureddatabindump>' % sys.argv[0])
            print('')
            print('This program will parse a binary dump of gameserver packets')
            print('such as the one written by gameclient.py, parses it and writes')
            print('the result into a text file with the same name as the input,')
            print('but with a _parsed.txt suffix')
            exit(0)

        infilename = sys.argv[1]
        
        main(infilename)
    except Exception as e:
        traceback.print_exc()
        time.sleep(5)
        sys.exit(-1)
