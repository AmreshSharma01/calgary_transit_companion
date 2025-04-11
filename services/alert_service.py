import requests
import logging
from google.transit import gtfs_realtime_pb2
import datetime

# Set up logging
logger = logging.getLogger(__name__)

def fetch_service_alerts(alert_url):
    alerts = []
    try:
        response = requests.get(alert_url)
        if response.status_code != 200:
            logger.error(f"Error fetching service alerts: {response.status_code} - {response.text}")
            return alerts
        feed = gtfs_realtime_pb2.FeedMessage()
        feed.ParseFromString(response.content)
        for entity in feed.entity:
            if entity.HasField('alert'):
                alert_data = {
                    'id': entity.id,
                    'effect': gtfs_realtime_pb2.Alert.Effect.Name(entity.alert.effect),
                    'cause': gtfs_realtime_pb2.Alert.Cause.Name(entity.alert.cause),
                    'header_text': _get_translated_text(entity.alert.header_text),
                    'description_text': _get_translated_text(entity.alert.description_text),
                    'url': _get_translated_text(entity.alert.url) if entity.alert.HasField('url') else None,
                    'severity_level': _get_severity_level(entity.alert.effect),
                    'active_period': _extract_active_periods(entity.alert.active_period),
                    'affected_entities': _extract_informed_entities(entity.alert.informed_entity)
                }
                alerts.append(alert_data)
                
        logger.info(f"Fetched {len(alerts)} service alerts")
        return alerts
        
    except Exception as e:
        logger.error(f"Exception fetching service alerts: {e}")
        return alerts

def filter_alerts_by_route(alerts, route_id):
    filtered_alerts = []
    
    for alert in alerts:
        for entity in alert['affected_entities']:
            if entity.get('route_id') == route_id:
                filtered_alerts.append(alert)
                break
                
    logger.info(f"Filtered {len(filtered_alerts)} alerts for route {route_id}")
    return filtered_alerts

def filter_alerts_by_stop(alerts, stop_id):
    filtered_alerts = []
    
    for alert in alerts:
        for entity in alert['affected_entities']:
            if entity.get('stop_id') == stop_id:
                filtered_alerts.append(alert)
                break
                
    logger.info(f"Filtered {len(filtered_alerts)} alerts for stop {stop_id}")
    return filtered_alerts

def get_active_alerts(alerts):
    active_alerts = []
    current_time = datetime.datetime.now().timestamp()
    
    for alert in alerts:
        is_active = False
        
        if not alert['active_period']:
            is_active = True
        else:
            for period in alert['active_period']:
                start = period.get('start')
                end = period.get('end')
                
                start_active = (start is None) or (current_time >= start)
                end_active = (end is None) or (current_time <= end)
                
                if start_active and end_active:
                    is_active = True
                    break
        
        if is_active:
            active_alerts.append(alert)
    
    logger.info(f"Found {len(active_alerts)} currently active alerts")
    return active_alerts

def _get_translated_text(translated_string):
    if not translated_string.translation:
        return ""
        
    for translation in translated_string.translation:
        if translation.language == "en":
            return translation.text
            
    return translated_string.translation[0].text

def _extract_active_periods(active_periods):
    periods = []
    
    for period in active_periods:
        period_data = {}
        
        if period.HasField('start'):
            period_data['start'] = period.start
            
        if period.HasField('end'):
            period_data['end'] = period.end
            
        periods.append(period_data)
        
    return periods

def _extract_informed_entities(entities):
    affected_entities = []
    
    for entity in entities:
        entity_data = {}
        
        if entity.HasField('agency_id'):
            entity_data['agency_id'] = entity.agency_id
            
        if entity.HasField('route_id'):
            entity_data['route_id'] = entity.route_id
            
        if entity.HasField('route_type'):
            entity_data['route_type'] = entity.route_type
            
        if entity.HasField('stop_id'):
            entity_data['stop_id'] = entity.stop_id
            
        if entity.HasField('trip'):
            entity_data['trip_id'] = entity.trip.trip_id
            
        affected_entities.append(entity_data)
        
    return affected_entities

def _get_severity_level(effect):
    high_severity = ['NO_SERVICE', 'REDUCED_SERVICE', 'SIGNIFICANT_DELAYS']
    medium_severity = ['DETOUR', 'STOP_MOVED', 'OTHER_EFFECT']
    low_severity = ['ADDITIONAL_SERVICE', 'MODIFIED_SERVICE', 'UNKNOWN_EFFECT']
    
    if effect in high_severity:
        return 'high'
    elif effect in medium_severity:
        return 'medium'
    else:
        return 'low'