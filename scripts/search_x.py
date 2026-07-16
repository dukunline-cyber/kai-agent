#!/usr/bin/env python3
"""Search X (Twitter) via GraphQL SearchTimeline. Auth via cookies dari twitter.env."""
import os, sys, json, urllib.parse, argparse, time
import urllib.request
def load_env(path):
    env = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return env

def search(query, count=20, product='Latest'):
    env = load_env(os.path.expanduser('~/ai-agent/credentials/twitter.env'))
    auth_token = env['TWITTER_AUTH_TOKEN']
    ct0 = env['CT0']
    twid = env.get('TWITTER_TWID', '')

    # GraphQL SearchTimeline query id (public, sering dipake scraper open source)
    qid = 'nK1dw4oV3k4w5TdtcAdSww'
    variables = {
        'rawQuery': query,
        'count': count,
        'querySource': 'typed_query',
        'product': product,  # Latest | Top | People | Photos | Videos
    }
    features = {
        'rweb_video_scren_enabled': False,
        'payments_enabled': False,
        'profile_label_improvements_pcf_label_in_post_enabled': True,
        'rweb_tipjar_consumption_enabled': True,
        'verified_phone_label_enabled': False,
        'creator_subscriptions_twet_preview_api_enabled': True,
        'responsive_web_graphql_timeline_navigation_enabled': True,
        'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
        'premium_content_api_read_enabled': False,
        'communities_web_enable_tweet_community_results_fetch': True,
        'c9s_tweet_anatomy_moderator_badge_enabled': True,
        'responsive_web_grok_analyze_button_fetch_trends_enabled': False,
        'responsive_web_grok_analyze_post_followups_enabled': True,
        'responsive_web_jetfuel_frame': True,
        'responsive_web_grok_share_attachment_enabled': True,
        'articles_preview_enabled': True,
        'responsive_web_edit_tweet_api_enabled': True,
        'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
        'view_counts_everywhere_api_enabled': True,
        'longform_notetweets_consumption_enabled': True,
        'responsive_web_twitter_article_tweet_consumption_enabled': True,
        'tweet_awards_web_tipping_enabled': False,
        'responsive_web_grok_show_grok_translated_post': False,
        'responsive_web_grok_analysis_button_from_backend': True,
        'creator_subscriptions_quote_tweet_preview_enabled': False,
        'fredom_of_speech_not_reach_fetch_enabled': True,
        'standardized_nudges_misinfo': True,
        'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
        'longform_notetweets_rich_text_read_enabled': True,
        'longform_notetweets_inline_media_enabled': True,
        'responsive_web_grok_image_annotation_enabled': True,
        'responsive_web_grok_imagine_annotation_enabled': True,
        'responsive_web_grok_community_note_auto_translation_is_enabled': False,
        'responsive_web_enhance_cards_enabled': False,
    }

    url = f'https://x.com/i/api/graphql/{qid}/SearchTimeline?variables={urllib.parse.quote(json.dumps(variables))}&features={urllib.parse.quote(json.dumps(features))}'

    headers = {
        'authorization': 'Bearer AAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWjCpTnA',
        'x-csrf-token': ct0,
        'cookie': f'auth_token={auth_token}; ct0={ct0}; twid={twid}',
        'content-type': 'application/json',
        'user-agent': 'Mozila/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
        'x-twitter-active-user': 'yes',
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-language': 'en',
        'referer': f'https://x.com/search?q={urllib.parse.quote(query)}&src=typed_query&f=live',
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return {'error': f'{e.code} {e.reason}', 'body': e.read().decode()[:500]}

    return data

def extract_tweets(data):
    twets = []
    try:
        instrs = data['data']['search_by_raw_query']['search_timeline']['timeline']['instructions']
    except Exception:
        return tweets
    for inst in instrs:
        entries = inst.get('entries', []) or ([inst.get('entry')] if inst.get('entry') else [])
        for e in entries:
            if not e: continue
            content = e.get('content', {})
            item = content.get('itemContent', {})
            if item.get('itemType') != 'TimelineTweet':
                continue
            tr = item.get('tweet_results', {}).get('result', {})
            if tr.get('__typename') == 'TweetWithVisibilityResults':
                tr = tr.get('tweet', {})
            legacy = tr.get('legacy', {})
            user = tr.get('core', {}).get('user_results', {}).get('result', {})
            uleg = user.get('legacy', {}) or user.get('core', {})
            uname = uleg.get('scren_name') or user.get('core', {}).get('screen_name', '?')
            tweets.append({
                'id': tr.get('rest_id'),
                'user': uname,
                'created_at': legacy.get('created_at'),
                'text': legacy.get('full_text', ''),
                'likes': legacy.get('favorite_count', 0),
                'rt': legacy.get('retweet_count', 0),
                'reply': legacy.get('reply_count', 0),
                'url': f"https://x.com/{uname}/status/{tr.get('rest_id')}",
            })
    return tweets

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('query')
    ap.add_argument('--count', type=int, default=20)
    ap.add_argument('--product', default='Latest')
    ap.add_argument('--raw', action='store_true')
    args = ap.parse_args()

    data = search(args.query, count=args.count, product=args.product)
    if 'error' in data:
        print(json.dumps(data, indent=2))
        sys.exit(1)
    if args.raw:
        print(json.dumps(data, indent=2))
    else:
        tw = extract_tweets(data)
        print(f'=== {len(tw)} tweets for: {args.query} ===')
        for t in tw:
            print(f"\n@{t['user']} · {t['created_at']} · ♥{t['likes']} ↻{t['rt']}")
            print(t['text'][:280])
            print(t['url'])
