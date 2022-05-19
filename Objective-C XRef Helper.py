
#objective-c xrefs hopper script
#rewrite the IDAPython script https://github.com/fireeye/flare-ida/blob/master/python/flare/objc2_xrefs_helper.py
#author: Kai Lu(@k3vinlusec)
#editor: Zhuoli Li(@dreampiggy)

def getRefPtr(doc,classMethodsVA,objcSelRefs, objcMsgRefs, objcConst):
	ret = (None, None)
	namePtr = doc.readUInt64LE(classMethodsVA) #get name field in struct __objc_method, it's selector
	ctn = 0

	for x in xrefsto(doc,namePtr):
		#print('xreffrom: ' + hex(x) ,'xrefto: ' + hex(namePtr))
		if objcSelRefs and x >= objcSelRefs[0] and x < objcSelRefs[1]:
			ret =(False, x)
		elif objcMsgRefs and x >=objcMsgRefs[0] and x < objcMsgRefs[1]:
			ret = (True, x)
		elif objcConst and x >= objcConst[0] and x < objcConst[1]:
			ctn += 1

	if ctn > 1:
		ret =(None, None)

	return ret

def xrefsto(doc,addr):
	xrefslist = []
	for i in range(doc.getSegmentCount()):
		seg = doc.getSegment(i)
		eachxrefs = seg.getReferencesOfAddress(addr)
		for x in eachxrefs:
			xrefslist.append(x)
	return xrefslist

def run():
	BADADDR = 0xFFFFFFFFFFFFFFFF
	objcData = None
	objcSelRefs = None
	objcMsgRefs = None
	objcConst = None
	objc2ClassSize = 0x28
	objc2ClassInfoOffs = 0x20
	objc2ClassMethSize = 0x18 # 3 x 8 bits
	objc2ClassRelativeMethSize = 0xC # 3 x 4 bits
	objc2ClassBaseMethOffs = 0x20
	objc2ClassMethImpOffs = 0x10 # 2 x 8 bits
	objc2ClassRelativeMethImpOffs = 0x8 # 2 * 4 bits

	doc = Document.getCurrentDocument()
	for i in range(doc.getSegmentCount()):
		seg = doc.getSegment(i)
		#print('[*]'+ seg.getName())
		for sect in seg.getSectionsList():
			sectName = sect.getName()
			if sectName == '__objc_data':
				objcData = (sect.getStartingAddress(),sect.getStartingAddress()+sect.getLength())
			elif sectName == '__objc_selrefs':
				objcSelRefs = (sect.getStartingAddress(),sect.getStartingAddress()+sect.getLength())
			elif sectName == '__objc_msgrefs':
				objcMsgRefs = (sect.getStartingAddress(),sect.getStartingAddress()+sect.getLength())
			elif sectName == '__objc_const':
				objcConst = (sect.getStartingAddress(),sect.getStartingAddress()+sect.getLength())
			else:
				pass
			#print('  +++' + sectName, (hex(sect.getStartingAddress()),hex(sect.getStartingAddress()+sect.getLength())))

	if((objcSelRefs != None or objcMsgRefs != None) and (objcData != None and objcConst != None)) == False:
		doc.log("could not find necessary Objective-C sections...\n")
		return

	#walk through classes
	for va in range(objcData[0],objcData[1],objc2ClassSize):
		classRoVA = doc.readUInt64LE(va + objc2ClassInfoOffs)

		if classRoVA == BADADDR or classRoVA == 0:
			continue

		classMethodsVA = doc.readUInt64LE(classRoVA + objc2ClassBaseMethOffs)

		if classMethodsVA == BADADDR or classMethodsVA == 0:
			continue

		flags = doc.readUInt32LE(classMethodsVA)
		count = doc.readUInt32LE(classMethodsVA + 4)
		classMethodsVA += 4*2

		#support __objc_relative_method
		# see: https://developer.apple.com/videos/play/wwdc2020/10163/?time=479
		# source code: https://github.com/apple-oss-distributions/objc4/blob/objc4-841.13/runtime/objc-runtime-new.h#L761

		#static const uint32_t smallMethodListFlag = 0x80000000;
		isRelativeMethodList = False
		if (flags & 0x80000000):
			isRelativeMethodList = True
		if isRelativeMethodList:
			print("Found Objective-C relateive method list. Fix it up...")

		#walk through methods
		if isRelativeMethodList:
			for va1 in range(classMethodsVA,classMethodsVA + objc2ClassRelativeMethSize * count, objc2ClassRelativeMethSize):
				# name = base + *(base + 0 * 4 bits)
				nameVA = va1 + doc.readUInt32LE(va1)
				#print('[*]start---------------')
				isMsgRef, selRefVA = getRefPtr(doc, nameVA, objcSelRefs, objcMsgRefs, objcConst)
				#print('[*]end------------------')
				if selRefVA == None:
					continue
				impOffs = doc.readUInt32LE(va1 + objc2ClassRelativeMethImpOffs)
				funcVA = va1 + impOffs - 0xFFFFFFF8

				if isMsgRef:
					selRefVA -= 8
				#print('selref VA: %08x - function VA: %08x\n' %(selRefVA, funcVA))
				for x in xrefsto(doc, selRefVA):
					doc.getSegmentAtAddress(x).addReference(x, funcVA)
		else:
			for va1 in range(classMethodsVA,classMethodsVA + objc2ClassMethSize * count, objc2ClassMethSize):
				nameVA = va1
				#print('[*]start---------------')
				isMsgRef, selRefVA = getRefPtr(doc, nameVA, objcSelRefs, objcMsgRefs, objcConst)
				#print(isMsgRef,selRefVA)
				#print('[*]end------------------')
				if selRefVA == None:
					continue
				funcVA = doc.readUInt64LE(va1 + objc2ClassMethImpOffs)

				if isMsgRef:
					selRefVA -= 8
				#print('selref VA: %08x - function VA: %08x\n' %(selRefVA, funcVA))
				for x in xrefsto(doc, selRefVA):
					doc.getSegmentAtAddress(x).addReference(x, funcVA)

if __name__ == '__main__':
	run()
