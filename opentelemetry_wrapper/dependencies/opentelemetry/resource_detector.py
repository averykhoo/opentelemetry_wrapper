from opentelemetry.sdk.resources import OTELResourceDetector


def get_resource_attributes():
    return OTELResourceDetector().detect().attributes
