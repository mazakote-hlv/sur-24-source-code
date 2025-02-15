from math import floor, modf

try:
    import utime
except ImportError:
    import time

class MicropyGPS:
    SENTENCE_LIMIT = 90
    __HEMISPHERES = ('N', 'S', 'E', 'W')
    __NO_FIX = 1
    __FIX_2D = 2
    __FIX_3D = 3
    __DIRECTIONS = ('N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW')
    __MONTHS = ('January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December')

    def __init__(self, local_offset=0, location_formatting='ddm'):
        self.sentence_active = False
        self.active_segment = 0
        self.process_crc = False
        self.gps_segments = []
        self.crc_xor = 0
        self.char_count = 0
        self.fix_time = 0
        self.crc_fails = 0
        self.clean_sentences = 0
        self.parsed_sentences = 0
        self.log_handle = None
        self.log_en = False
        self.timestamp = [0, 0, 0.0]
        self.date = [0, 0, 0]
        self.local_offset = local_offset
        self._latitude = [0, 0.0, 'N']
        self._longitude = [0, 0.0, 'W']
        self.coord_format = location_formatting
        self.speed = [0.0, 0.0, 0.0]
        self.course = 0.0
        self.altitude = 0.0
        self.geoid_height = 0.0
        self.satellites_in_view = 0
        self.satellites_in_use = 0
        self.satellites_used = []
        self.last_sv_sentence = 0
        self.total_sv_sentences = 0
        self.satellite_data = dict()
        self.hdop = 0.0
        self.pdop = 0.0
        self.vdop = 0.0
        self.valid = False
        self.fix_stat = 0
        self.fix_type = 1

    @property
    def latitude(self):
        if self.coord_format == 'dd':
            decimal_degrees = self._latitude[0] + (self._latitude[1] / 60)
            return [decimal_degrees, self._latitude[2]]
        elif self.coord_format == 'dms':
            minute_parts = modf(self._latitude[1])
            seconds = round(minute_parts[0] * 60)
            return [self._latitude[0], int(minute_parts[1]), seconds, self._latitude[2]]
        else:
            return self._latitude

    @property
    def longitude(self):
        if self.coord_format == 'dd':
            decimal_degrees = self._longitude[0] + (self._longitude[1] / 60)
            return [decimal_degrees, self._longitude[2]]
        elif self.coord_format == 'dms':
            minute_parts = modf(self._longitude[1])
            seconds = round(minute_parts[0] * 60)
            return [self._longitude[0], int(minute_parts[1]), seconds, self._longitude[2]]
        else:
            return self._longitude

    def start_logging(self, target_file, mode="append"):
        mode_code = 'w' if mode == 'new' else 'a'
        try:
            self.log_handle = open(target_file, mode_code)
        except AttributeError:
            return False
        self.log_en = True
        return True

    def stop_logging(self):
        try:
            self.log_handle.close()
        except AttributeError:
            return False
        self.log_en = False
        return True

    def write_log(self, log_string):
        try:
            self.log_handle.write(log_string)
        except TypeError:
            return False
        return True

    def gprmc(self):
        try:
            utc_string = self.gps_segments[1]
            if utc_string:
                hours = (int(utc_string[0:2]) + self.local_offset) % 24
                minutes = int(utc_string[2:4])
                seconds = float(utc_string[4:])
                self.timestamp = [hours, minutes, seconds]
            else:
                self.timestamp = [0, 0, 0.0]
        except ValueError:
            return False

        try:
            date_string = self.gps_segments[9]
            if date_string:
                day = int(date_string[0:2])
                month = int(date_string[2:4])
                year = int(date_string[4:6])
                self.date = (day, month, year)
            else:
                self.date = (0, 0, 0)
        except ValueError:
            return False

        if self.gps_segments[2] == 'A':
            try:
                l_string = self.gps_segments[3]
                lat_degs = int(l_string[0:2])
                lat_mins = float(l_string[2:])
                lat_hemi = self.gps_segments[4]
                l_string = self.gps_segments[5]
                lon_degs = int(l_string[0:3])
                lon_mins = float(l_string[3:])
                lon_hemi = self.gps_segments[6]
            except ValueError:
                return False

            if lat_hemi not in self.__HEMISPHERES or lon_hemi not in self.__HEMISPHERES:
                return False

            try:
                spd_knt = float(self.gps_segments[7])
            except ValueError:
                return False

            try:
                course = float(self.gps_segments[8]) if self.gps_segments[8] else 0.0
            except ValueError:
                return False

            self._latitude = [lat_degs, lat_mins, lat_hemi]
            self._longitude = [lon_degs, lon_mins, lon_hemi]
            self.speed = [spd_knt, spd_knt * 1.151, spd_knt * 1.852]
            self.course = course
            self.valid = True
            self.new_fix_time()
        else:
            self._latitude = [0, 0.0, 'N']
            self._longitude = [0, 0.0, 'W']
            self.speed = [0.0, 0.0, 0.0]
            self.course = 0.0
            self.valid = False
        return True

    def gpgll(self):
        try:
            utc_string = self.gps_segments[5]
            if utc_string:
                hours = (int(utc_string[0:2]) + self.local_offset) % 24
                minutes = int(utc_string[2:4])
                seconds = float(utc_string[4:])
                self.timestamp = [hours, minutes, seconds]
            else:
                self.timestamp = [0, 0, 0.0]
        except ValueError:
            return False

        if self.gps_segments[6] == 'A':
            try:
                l_string = self.gps_segments[1]
                lat_degs = int(l_string[0:2])
                lat_mins = float(l_string[2:])
                lat_hemi = self.gps_segments[2]
                l_string = self.gps_segments[3]
                lon_degs = int(l_string[0:3])
                lon_mins = float(l_string[3:])
                lon_hemi = self.gps_segments[4]
            except ValueError:
                return False

            if lat_hemi not in self.__HEMISPHERES or lon_hemi not in self.__HEMISPHERES:
                return False

            self._latitude = [lat_degs, lat_mins, lat_hemi]
            self._longitude = [lon_degs, lon_mins, lon_hemi]
            self.valid = True
            self.new_fix_time()
        else:
            self._latitude = [0, 0.0, 'N']
            self._longitude = [0, 0.0, 'W']
            self.valid = False
        return True

    def gpvtg(self):
        try:
            course = float(self.gps_segments[1]) if self.gps_segments[1] else 0.0
            spd_knt = float(self.gps_segments[5]) if self.gps_segments[5] else 0.0
        except ValueError:
            return False

        self.speed = (spd_knt, spd_knt * 1.151, spd_knt * 1.852)
        self.course = course
        return True

    def gpgga(self):
        try:
            utc_string = self.gps_segments[1]
            if utc_string:
                hours = (int(utc_string[0:2]) + self.local_offset) % 24
                minutes = int(utc_string[2:4])
                seconds = float(utc_string[4:])
            else:
                hours = 0
                minutes = 0
                seconds = 0.0

            satellites_in_use = int(self.gps_segments[7])
            fix_stat = int(self.gps_segments[6])
        except (ValueError, IndexError):
            return False

        try:
            hdop = float(self.gps_segments[8])
        except (ValueError, IndexError):
            hdop = 0.0

        if fix_stat:
            try:
                l_string = self.gps_segments[2]
                lat_degs = int(l_string[0:2])
                lat_mins = float(l_string[2:])
                lat_hemi = self.gps_segments[3]
                l_string = self.gps_segments[4]
                lon_degs = int(l_string[0:3])
                lon_mins = float(l_string[3:])
                lon_hemi = self.gps_segments[5]
            except ValueError:
                return False

            if lat_hemi not in self.__HEMISPHERES or lon_hemi not in self.__HEMISPHERES:
                return False

            try:
                altitude = float(self.gps_segments[9])
                geoid_height = float(self.gps_segments[11])
            except ValueError:
                altitude = 0
                geoid_height = 0

            self._latitude = [lat_degs, lat_mins, lat_hemi]
            self._longitude = [lon_degs, lon_mins, lon_hemi]
            self.altitude = altitude
            self.geoid_height = geoid_height

        self.timestamp = [hours, minutes, seconds]
        self.satellites_in_use = satellites_in_use
        self.hdop = hdop
        self.fix_stat = fix_stat

        if fix_stat:
            self.new_fix_time()

        return True

    def gpgsa(self):
        try:
            fix_type = int(self.gps_segments[2])
        except ValueError:
            return False

        sats_used = []
        for sats in range(12):
            sat_number_str = self.gps_segments[3 + sats]
            if sat_number_str:
                try:
                    sat_number = int(sat_number_str)
                    sats_used.append(sat_number)
                except ValueError:
                    return False
            else:
                break

        try:
            pdop = float(self.gps_segments[15])
            hdop = float(self.gps_segments[16])
            vdop = float(self.gps_segments[17])
        except ValueError:
            return False

        self.fix_type = fix_type

        if fix_type > self.__NO_FIX:
            self.new_fix_time()

        self.satellites_used = sats_used
        self.hdop = hdop
        self.vdop = vdop
        self.pdop = pdop

        return True

    def gpgsv(self):
        try:
            num_sv_sentences = int(self.gps_segments[1])
            current_sv_sentence = int(self.gps_segments[2])
            sats_in_view = int(self.gps_segments[3])
        except ValueError:
            return False

        satellite_dict = dict()

        if num_sv_sentences == current_sv_sentence:
            sat_segment_limit = (sats_in_view - ((num_sv_sentences - 1) * 4)) * 5
        else:
            sat_segment_limit = 20

        for sats in range(4, sat_segment_limit, 4):
            if self.gps_segments[sats]:
                try:
                    sat_id = int(self.gps_segments[sats])
                except (ValueError, IndexError):
                    return False

                try:
                    elevation = int(self.gps_segments[sats + 1])
                except (ValueError, IndexError):
                    elevation = None

                try:
                    azimuth = int(self.gps_segments[sats + 2])
                except (ValueError, IndexError):
                    azimuth = None

                try:
                    snr = int(self.gps_segments[sats + 3])
                except (ValueError, IndexError):
                    snr = None
            else:
                break

            satellite_dict[sat_id] = (elevation, azimuth, snr)

        self.total_sv_sentences = num_sv_sentences
        self.last_sv_sentence = current_sv_sentence
        self.satellites_in_view = sats_in_view

        if current_sv_sentence == 1:
            self.satellite_data = satellite_dict
        else:
            self.satellite_data.update(satellite_dict)

        return True

    def new_sentence(self):
        self.gps_segments = ['']
        self.active_segment = 0
        self.crc_xor = 0
        self.sentence_active = True
        self.process_crc = True
        self.char_count = 0

    def update(self, new_char):
        valid_sentence = False
        ascii_char = ord(new_char)

        if 10 <= ascii_char <= 126:
            self.char_count += 1

            if self.log_en:
                self.write_log(new_char)

            if new_char == '$':
                self.new_sentence()
                return None

            elif self.sentence_active:
                if new_char == '*':
                    self.process_crc = False
                    self.active_segment += 1
                    self.gps_segments.append('')
                    return None

                elif new_char == ',':
                    self.active_segment += 1
                    self.gps_segments.append('')

                else:
                    self.gps_segments[self.active_segment] += new_char

                    if not self.process_crc:
                        if len(self.gps_segments[self.active_segment]) == 2:
                            try:
                                final_crc = int(self.gps_segments[self.active_segment], 16)
                                if self.crc_xor == final_crc:
                                    valid_sentence = True
                                else:
                                    self.crc_fails += 1
                            except ValueError:
                                pass

                if self.process_crc:
                    self.crc_xor ^= ascii_char

                if valid_sentence:
                    self.clean_sentences += 1
                    self.sentence_active = False

                    if self.gps_segments[0] in self.supported_sentences:
                        if self.supported_sentences[self.gps_segments[0]](self):
                            self.parsed_sentences += 1
                            return self.gps_segments[0]

                if self.char_count > self.SENTENCE_LIMIT:
                    self.sentence_active = False

        return None

    def new_fix_time(self):
        try:
            self.fix_time = utime.ticks_ms()
        except NameError:
            self.fix_time = time.time()

    def satellite_data_updated(self):
        return self.total_sv_sentences > 0 and self.total_sv_sentences == self.last_sv_sentence

    def unset_satellite_data_updated(self):
        self.last_sv_sentence = 0

    def satellites_visible(self):
        return list(self.satellite_data.keys())

    def time_since_fix(self):
        if self.fix_time == 0:
            return -1

        try:
            current = utime.ticks_diff(utime.ticks_ms(), self.fix_time)
        except NameError:
            current = (time.time() - self.fix_time) * 1000

        return current

    def compass_direction(self):
        if self.course >= 348.75:
            offset_course = 360 - self.course
        else:
            offset_course = self.course + 11.25

        dir_index = floor(offset_course / 22.5)
        final_dir = self.__DIRECTIONS[dir_index]
        return final_dir

    def latitude_string(self):
        if self.coord_format == 'dd':
            formatted_latitude = self.latitude
            lat_string = str(formatted_latitude[0]) + '° ' + str(self._latitude[2])
        elif self.coord_format == 'dms':
            formatted_latitude = self.latitude
            lat_string = str(formatted_latitude[0]) + '° ' + str(formatted_latitude[1]) + "' " + str(formatted_latitude[2]) + '" ' + str(formatted_latitude[3])
        else:
            lat_string = str(self._latitude[0]) + '° ' + str(self._latitude[1]) + "' " + str(self._latitude[2])
        return lat_string

    def longitude_string(self):
        if self.coord_format == 'dd':
            formatted_longitude = self.longitude
            lon_string = str(formatted_longitude[0]) + '° ' + str(self._longitude[2])
        elif self.coord_format == 'dms':
            formatted_longitude = self.longitude
            lon_string = str(formatted_longitude[0]) + '° ' + str(formatted_longitude[1]) + "' " + str(formatted_longitude[2]) + '" ' + str(formatted_longitude[3])
        else:
            lon_string = str(self._longitude[0]) + '° ' + str(self._longitude[1]) + "' " + str(self._longitude[2])
        return lon_string

    def speed_string(self, unit='kph'):
        if unit == 'mph':
            speed_string = str(self.speed[1]) + ' mph'
        elif unit == 'knot':
            unit_str = ' knot' if self.speed[0] == 1 else ' knots'
            speed_string = str(self.speed[0]) + unit_str
        else:
            speed_string = str(self.speed[2]) + ' km/h'
        return speed_string

    def date_string(self, formatting='s_mdy', century='20'):
        if formatting == 'long':
            month = self.__MONTHS[self.date[1] - 1]
            if self.date[0] in (1, 21, 31):
                suffix = 'st'
            elif self.date[0] in (2, 22):
                suffix = 'nd'
            elif self.date[0] == (3, 23):
                suffix = 'rd'
            else:
                suffix = 'th'
            day = str(self.date[0]) + suffix
            year = century + str(self.date[2])
            date_string = month + ' ' + day + ', ' + year
        else:
            day = '0' + str(self.date[0]) if self.date[0] < 10 else str(self.date[0])
            month = '0' + str(self.date[1]) if self.date[1] < 10 else str(self.date[1])
            year = '0' + str(self.date[2]) if self.date[2] < 10 else str(self.date[2])
            if formatting == 's_dmy':
                date_string = day + '/' + month + '/' + year
            else:
                date_string = month + '/' + day + '/' + year
        return date_string

    supported_sentences = {
        'GPRMC': gprmc, 'GLRMC': gprmc,
        'GPGGA': gpgga, 'GLGGA': gpgga,
        'GPVTG': gpvtg, 'GLVTG': gpvtg,
        'GPGSA': gpgsa, 'GLGSA': gpgsa,
        'GPGSV': gpgsv, 'GLGSV': gpgsv,
        'GPGLL': gpgll, 'GLGLL': gpgll,
        'GNGGA': gpgga, 'GNRMC': gprmc,
        'GNVTG': gpvtg, 'GNGLL': gpgll,
        'GNGSA': gpgsa,
    }
