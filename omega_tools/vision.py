"""Typed vision-provider adapter; model quality needs a separate held-out corpus."""
import base64,hashlib
def describe(image,provider,*,capability,verifier,principal):
    verifier.require(capability,principal,'vision.infer')
    if type(image) is not bytes or not 0<len(image)<=16*1024**2:raise ValueError('Image byte budget exceeded')
    digest=hashlib.sha256(image).hexdigest()
    response=provider({'image_base64':base64.b64encode(image).decode(),'sha256':digest,'input_is_untrusted_data':True})
    if type(response) is not dict or set(response)!={'description','objects'} or type(response['description']) is not str or type(response['objects']) is not list or len(response['description'])>32768 or len(response['objects'])>1024:raise ValueError('Invalid vision response')
    for item in response['objects']:
        if type(item) is not dict or set(item)!={'label','confidence','box'} or type(item['label']) is not str:raise ValueError('Malformed vision object')
        if not 0<=item['confidence']<=1 or len(item['box'])!=4 or any(not 0<=v<=1 for v in item['box']):raise ValueError('Invalid vision object geometry')
    return {**response,'source_sha256':digest,'authority':False}
