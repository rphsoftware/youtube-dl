# coding: utf-8

from __future__ import unicode_literals

from .common import InfoExtractor

from ..compat import compat_urllib_parse

from ..utils import ExtractorError

import re
import time
import uuid
import math
import random
import zlib
import hashlib

class IqiyiIE(InfoExtractor):
    IE_NAME = 'iqiyi'

    _VALID_URL = r'http://(?:www\.)iqiyi.com/.+?\.html'

    _TEST = {
            'url': 'http://www.iqiyi.com/v_19rrojlavg.html',
            'md5': '2cb594dc2781e6c941a110d8f358118b',
            'info_dict': {
                'id': '9c1fb1b99d192b21c559e5a1a2cb3c73',
                'title': '美国德州空中惊现奇异云团 酷似UFO',
                'ext': 'f4v',
            }
    }

    def construct_video_urls(self, data, video_id, _uuid, bid):
        def do_xor(x, y):
            a = y % 3
            if a == 1:
                return x ^ 121
            if a == 2:
                return x ^ 72
            return x ^ 103

        def get_encode_code(l):
            a = 0
            b = l.split('-')
            c = len(b)
            s = ''
            for i in range(c - 1, -1, -1):
                a = do_xor(int(b[c-i-1], 16), i)
                s += chr(a)
            return s[::-1]

        def get_path_key(x):
            mg = ')(*&^flash@#$%a'
            tm = self._download_json(
                'http://data.video.qiyi.com/t?tn=' + str(random.random()), video_id)['t']
            t = str(int(math.floor(int(tm)/(600.0))))
            return hashlib.md5(
                 (t+mg+x).encode('utf8')).hexdigest()

        # get accept format
        # getting all format will spend minutes for a big video.
        if bid == 'best':
            bids = [int(i['bid']) for i in data['vp']['tkl'][0]['vs'] \
                   if 0 < int(i['bid']) <= 10]
            bid = str(max(bids))

        video_urls_dict = {}
        for i in data['vp']['tkl'][0]['vs']:
            if 0 < int(i['bid']) <= 10:
                format_id = self.get_format(i['bid'])
            else:
                continue

            video_urls = []

            video_urls_info = i['fs']
            if not i['fs'][0]['l'].startswith('/'):
                t = get_encode_code(i['fs'][0]['l'])
                if t.endswith('mp4'):
                    video_urls_info = i['flvs']

            if int(i['bid']) != int(bid):  # ignore missing match format
                video_urls.extend(
                    [('http://example.com/v.flv', ii['b']) for ii in video_urls_info])
                video_urls_dict[format_id] = video_urls
                continue

            for ii in video_urls_info:
                vl = ii['l']
                if not vl.startswith('/'):
                    vl = get_encode_code(vl)
                key = get_path_key(
                    vl.split('/')[-1].split('.')[0])
                filesize = ii['b']
                base_url = data['vp']['du'].split('/')
                base_url.insert(-1, key)
                base_url = '/'.join(base_url)
                param = {
                    'su': _uuid,
                    'qyid': uuid.uuid4().hex,
                    'client': '',
                    'z': '',
                    'bt': '',
                    'ct': '',
                    'tn': str(int(time.time()))
                }
                api_video_url = base_url + vl + '?' + \
                    compat_urllib_parse.urlencode(param)
                js = self._download_json(api_video_url, video_id)
                video_url = js['l']
                video_urls.append(
                    (video_url, filesize))

            video_urls_dict[format_id] = video_urls
        return video_urls_dict

    def get_format(self, bid):
        _dict = {
            '1'  : 'h6',
            '2'  : 'h5',
            '3'  : 'h4',
            '4'  : 'h3',
            '5'  : 'h2',
            '10' : 'h1'
        }
        return _dict.get(str(bid), None)

    def get_bid(self, format_id):
        _dict = {
            'h6'   : '1',
            'h5'   : '2',
            'h4'   : '3',
            'h3'   : '4',
            'h2'   : '5',
            'h1'   : '10',
            'best' : 'best'
        }
        return _dict.get(format_id, None)

    def get_raw_data(self, tvid, video_id, enc_key, _uuid):
        tm = str(int(time.time()))
        param = {
            'key': 'fvip',
            'src': hashlib.md5(b'youtube-dl').hexdigest(),
            'tvId': tvid,
            'vid': video_id,
            'vinfo': 1,
            'tm': tm,
            'enc': hashlib.md5(
                (enc_key + tm + tvid).encode('utf8')).hexdigest(),
            'qyid': _uuid,
            'tn': random.random(),
            'um': 0,
            'authkey': hashlib.md5(
                (tm + tvid).encode('utf8')).hexdigest()
        }

        api_url = 'http://cache.video.qiyi.com/vms' + '?' + \
            compat_urllib_parse.urlencode(param)
        raw_data = self._download_json(api_url, video_id)
        return raw_data

    def get_enc_key(self, swf_url, video_id):
        req = self._request_webpage(
            swf_url, video_id, note='download swf content')
        cn = req.read()
        cn = zlib.decompress(cn[8:])
        pt = re.compile(b'MixerRemote\x08(?P<enc_key>.+?)\$&vv')
        enc_key = self._search_regex(pt, cn, 'enc_key').decode('utf8')
        return enc_key

    def _real_extract(self, url):
        webpage = self._download_webpage(
            url, 'temp_id', note='download video page')
        tvid = self._search_regex(
            r'tvId ?= ?(\'|\")(?P<tvid>\d+)', webpage, 'tvid', flags=re.I, group='tvid')
        video_id = self._search_regex(
            r'videoId ?= ?(\'|\")(?P<video_id>[a-z\d]+)',
            webpage, 'video_id', flags=re.I, group='video_id')
        swf_url = self._search_regex(
            r'(?P<swf>http://.+?MainPlayer.+?\.swf)', webpage, 'swf')
        _uuid = uuid.uuid4().hex

        enc_key = self.get_enc_key(swf_url, video_id)

        raw_data = self.get_raw_data(tvid, video_id, enc_key, _uuid)
        assert raw_data['code'] == 'A000000'
        if not raw_data['data']['vp']['tkl']:
            raise ExtractorError('No support iQiqy VIP video')

        data = raw_data['data']

        title = data['vi']['vn']

        format = self._downloader.params.get('format', None)
        bid = self.get_bid(format) if format else 'best'
        if not bid:
            raise ExtractorError('Can\'t get format.')

        # generate video_urls_dict
        video_urls_dict = self.construct_video_urls(
            data, video_id, _uuid, bid)

        # construct info
        entries = []
        for format_id in video_urls_dict:
            video_urls = video_urls_dict[format_id]
            for i, video_url_info in enumerate(video_urls):
                if len(entries) < i+1:
                    entries.append({'formats': []})
                entries[i]['formats'].append(
                    {
                        'url': video_url_info[0],
                        'filesize': video_url_info[-1],
                        'format_id': format_id,
                        'preference': int(self.get_bid(format_id))
                    }
                )

        for i in range(len(entries)):
            self._sort_formats(entries[i]['formats'])
            entries[i].update(
                {
                    'id': '_part%d' % (i+1),
                    'title': title,
                }
            )

        if len(entries) > 1:
            info = {
                '_type': 'multi_video',
                'id': video_id,
                'title': title,
                'entries': entries,
            }
        else:
            info = entries[0]
            info['id'] = video_id
            info['title'] = title

        return info
