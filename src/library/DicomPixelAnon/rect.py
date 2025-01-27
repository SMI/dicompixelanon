""" Rectangle classes.
  Rect is the base class, holding only a rectangle (top, bottom, left, right).
  It also has 'contains' methods to test if a given rectangle is inside.
  DicomRect is a subclass which also holds frame, overlay properties.
  It also overrides the 'contains' method to check frame,overlay match.
  DicomOcrRect is a subclass which also holds output from OCR and NER
  tests for PII.
"""

from copy import deepcopy
try:
    from fastDamerauLevenshtein import damerauLevenshtein
except:
    damerauLevenshtein = False


class Rect:
    """ Holds one rectangle.
    Coordinates start at 0, top left.
    Negative coordinates represent a null/invalid rectangle.
    """
    def __init__(self, top = -1, bottom = -1, left = -1, right = -1):
        self.top, self.bottom, self.left, self.right = top, bottom, left, right

    def __repr__(self):
        return '<Rect %d,%d->%d,%d>' % (self.left, self.top, self.right, self.bottom)

    def __eq__(self, other):
        return (self.T() == other.T() and
            self.B() == other.B() and
            self.L() == other.L() and
            self.R() == other.R())

    def set_rect(self, t, b, l, r):
        self.top, self.bottom, self.left, self.right = t, b, l, r
        return self

    def get_rect(self):
        return self.top, self.bottom, self.left, self.right

    def is_valid(self):
        if (self.top < 0 or self.bottom <= self.top or
            self.left < 0 or self.right <= self.left):
            return False
        return True

    def ltrb(self):
        return (self.left, self.top, self.right, self.bottom)

    def ltwh(self):
        return (self.left, self.top, 1 + self.right - self.left, 1 + self.bottom - self.top)

    def T(self):
        return self.top
    def B(self):
        return self.bottom
    def L(self):
        return self.left
    def R(self):
        return self.right

    def contains(self, x, y):
        """ Check if the given coordinate is inside this rectangle.
        """
        inside = (x >= self.left and x <= self.right and y >= self.top and y <= self.bottom)
        return inside

    def contains_rect(self, other_rect):
        """ Check if the given rectangle is fully inside (or equal to) this rectangle.
        """
        t,b,l,r = other_rect.get_rect()
        return self.contains(l, t) and self.contains(r, b)

    def intersect_rect(self, other_rect):
        """ Return a Rect which is the intersection of this rect with another.
        If no intersection then a null Rect is returned.
        """
        left = max(self.L(), other_rect.L())
        right = min(self.R(), other_rect.R())
        top = max(self.T(), other_rect.T())
        bottom = min(self.B(), other_rect.B())
        if left < right and top < bottom:
            return Rect(top = top, bottom = top + (bottom-top), left = left, right = left + (right-left))
        else:
            return Rect()

    def similar(self, other_rect):
        """ Check if this rect is almost identical to other_rect,
        within 2 pixels, and if so change self dimensions to be the
        larger of the two rectangles, and the longer of the text strings
        so that other_rect can be ignored. Return True if so.
        It is undefined if the two Rects are not of the same class.
        """
        t,b,l,r = self.get_rect()
        T,B,L,R = other_rect.get_rect()
        lim = 4 # was 2 but have seen examples in the wild needing 4
        # Compare coordinates
        if (abs(T-t) > lim) or (abs(L-l) > lim) or (abs(B-b) > lim) or (abs(R-r) > lim):
            return False
        return True

    def make_mbr(self, other_rect):
        """ Make the current rectangle the Minimum Bounding Rectangle
        of itself with other_rect.
        """
        t,b,l,r = self.get_rect()
        T,B,L,R = other_rect.get_rect()
        self.set_rect(min(T,t), max(B,b), min(L,l), max(R,r))


# ---------------------------------------------------------------------

class DicomRect(Rect):
    """ Holds one rectangle and which image frame/overlay it applies to.
    Coordinates start at 0, top left.
    -1 means unset or not applicable for frame/overlay number.
    Overlay = -1 means frame is a standard frame.
    Overlay >= 0 means frame is within that overlay.
    """
    def __init__(self, top = None, bottom = None, left = None, right = None, frame = -1, overlay = -1, arect = None):
        if arect:
            super().__init__(arect.T(), arect.B(), arect.L(), arect.R())
        elif top != None:
            super().__init__(top, bottom, left, right)
        else:
            super().__init__()
        self.frame, self.overlay = frame, overlay

    def __repr__(self):
        return '<DicomRect frame=%d overlay=%d %d,%d->%d,%d>' % (self.frame, self.overlay, self.left, self.top, self.right, self.bottom)

    def __eq__(self, other):
        # XXX does not check that other isinstance(DicomRect)
        return (super().__eq__(other) and
            self.F() == other.F() and
            self.O() == other.O())

    def F(self):
        return self.frame

    def O(self):
        return self.overlay

    def contains(self, x, y, frame = -1, overlay = -1):
        """ Check if the given coordinate is inside this rectangle,
        and the frame,overlay, if given, match this object.
        """
        rc = True
        if frame != -1 and frame != self.frame: rc = False
        if overlay != -1 and overlay != self.overlay: rc = False
        if not super().contains(x,y): rc = False
        return rc

    def similar(self, other_rect : 'DicomRect'):
        """ See Rect.similar(), this also checks that the two rectangles
        have the same frame and overlay
        """
        if not super().similar(other_rect):
            return False
        if (self.F() != other_rect.F()) or (self.O() != other_rect.O()):
            return False
        return True


# ---------------------------------------------------------------------

class DicomRectText(DicomRect):
    """ As a DicomRect but also holds details of any text found within,
    including the text, the source of the text, and whether it's PII.
    Right now ocrengine (enum), ocrtext (str), nerengine (enum), nerpii (enum)
    are all considered together so returned as a tuple from text_tuple().
    """
    pii_not_checked = -1
    pii_not_found = 0
    pii_possible = 1

    def __init__(self, top = None, bottom = None, left = None, right = None, frame = -1, overlay = -1, ocrengine = -1, ocrtext='', nerengine = 0, nerpii = -1, arect = None, dicomrect = None):
        if dicomrect:
            super.__init__(dicomrect.T(), dicomrect.B(), dicomrect.L(), dicomrect.R(), dicomrect.F(), dicomrect.O())
        elif arect:
            super().__init__(arect.T(), arect.B(), arect.L(), arect.R(), frame, overlay)
        elif top != None:
            super().__init__(top, bottom, left, right, frame, overlay)
        else:
            super().__init__()
        self.ocrengine, self.ocrtext = ocrengine, ocrtext
        self.nerengine, self.nerpii  = nerengine, nerpii

    def __repr__(self):
        return '<DicomRectText frame=%d overlay=%d %d,%d->%d,%d %d="%s" %d=%d>' % (self.frame, self.overlay, self.left, self.top, self.right, self.bottom,
            self.ocrengine, self.ocrtext, self.nerengine, self.nerpii)

    def __eq__(self, other):
        otherengine, othertext, otherner, otherpii = other.text_tuple()
        return (super().__eq__(other) and self.ocrtext == othertext)

    def text_tuple(self):
        """ Returns a tuple (ocrengine, ocrtext, nerengine, nerpii)
        """
        return self.ocrengine, self.ocrtext, self.nerengine, self.nerpii

    def similar(self, other_rect : 'DicomRectText'):
        """ See DicomRect.similar() but this also checks that the two rectangles
        have the same ocrtext, or very similar
        """
        if not super().similar(other_rect):
            return False
        sim_lim = 0.9 # text must be very similar to be same rectangle
        _, txt, _, _ = self.text_tuple()
        _, TXT, _, _ = other_rect.text_tuple()
        if damerauLevenshtein == False:
            return txt == TXT
        txt_sim = damerauLevenshtein(txt, TXT, similarity=True)
        if txt_sim < sim_lim:
            return False
        return True


# ---------------------------------------------------------------------

def test_similar():
    r1 = Rect(10,20,30,40)
    r2 = Rect(13,17,33,38)
    r3 = Rect(13,17,33,35)
    assert(r1.similar(r2) == True)
    assert(r1.similar(r3) == False)
    assert(r2.similar(r3) == True)
    r4 = DicomRect(10,20,30,40,2,3)
    r5 = DicomRect(11,21,31,41,2,3)
    r6 = DicomRect(12,22,33,44,2,4)
    assert(r4.similar(r5) == True)
    assert(r4.similar(r6) == False)
    assert(r5.similar(r6) == False)
    r7 = DicomRectText(10,20,30,40,2,3,-1,'jane maclean')
    r8 = DicomRectText(10,20,30,40,2,3,-1,'jane maclan')
    r9 = DicomRectText(10,20,30,40,2,3,-1,'jane macla')
    assert(r7.similar(r8) == True)
    assert(r7.similar(r9) == False)
    assert(r8.similar(r9) == True)
    r4.make_mbr(r6)
    assert(r4.get_rect() == (10,22,30,44))


# ---------------------------------------------------------------------

def rect_is_huge_font(rect):
    """
    Returns True if the rect has an area which is very much larger
    than the amount of text would suggest, implying that the font is
    extremely large, and thus that the OCR has picked up something
    which is most likely not normal text.
    Returns False if not sure, e.g. if not a DicomRectText object.
    """
    if not isinstance(rect, DicomRectText):
        return False
    if rect.L() == -1:
        return False
    (E,text,N,P) = rect.text_tuple()
    if not text:
        return False
    # Longer text is most likely genuine and widely spaced
    # due to the use of paragraph=True in easyocr
    if len(text) > 5:
        return False
    if (rect.R() - rect.L()) * (rect.B() - rect.T()) > 3000 * len(text):
        #print('ignore rect with text %s' % text)
        return True
    return False


# ---------------------------------------------------------------------

def filter_DicomRectText_list_by_fontsize(rectlist):
    """ Return a new list containing the rectangles from rectlist
    which do not contain text in a huge font, i.e. a small number of
    characters in a very large area. This is to filter out rectangles
    where OCR thinks it's found some text but probably hasn't.
    """
    retlist = [ rect for rect in rectlist if not rect_is_huge_font(rect) ]
    return retlist


# ---------------------------------------------------------------------

def add_Rect_to_list(rectlist, addrect, coalesce_similar = False):
    """ Extend the given list of rectangles with the given rectangle.
    Handles overlaps to ensure that the list does not contain any
    rectangles which would lie inside a larger rectangle.
    Works with Rect or DicomRect or DicomRectText objects.
    If coalesce_similar is True then a "similar" rectangle will not be
    added to the list if one already exists, the existing one will be
    enlarged to the minimum bounding rectangle of both, and the ocrtext
    will be the longer of the two strings.
    XXX doesn't check the frame/overlay because
    we assume there's a different list for every frame/overlay
    XXX doesn't check the ocrtext so will throw away text if it's
    in a rectangle which is inside one that is already in the list.
    """
    # If new rectangle is empty then do nothing
    if not addrect.is_valid():
        return
    # If this one is larger we need to remove ALL smaller rects from the existing list
    rectlist[:] = [
        rect for rect in rectlist if
            not addrect.contains_rect(rect)
    ]
    # Ignore if it's smaller than an existing one
    for rect in rectlist:
        # If a larger rectangle already exists then ignore this one
        if rect.contains_rect(addrect):
            return
    # Modify an existing one if the new one is similar
    if coalesce_similar:
        for rect in rectlist:
            if rect.similar(addrect):
                rect.make_mbr(addrect)
                return
    rectlist.append(addrect)


def test_add_Rect_to_list():
    l1 = []
    add_Rect_to_list(l1, DicomRectText(10,20,30,40,1,2,-1,'jane macleod'), coalesce_similar = True)
    add_Rect_to_list(l1, DicomRectText(100,200,300,400,1,2,-1,'jane macleod'), coalesce_similar = True)
    add_Rect_to_list(l1, DicomRectText(8,19,28,42,1,2,-1,'jane mcleod'), coalesce_similar = True)
    assert(str(l1) == 
        '[<DicomRectText frame=1 overlay=2 28,8->42,20 -1="jane macleod" 0=-1>, <DicomRectText frame=1 overlay=2 300,100->400,200 -1="jane macleod" 0=-1>]')


# ---------------------------------------------------------------------

def rect_exclusive_list(rectlist, width, height):
    """ Return a set of rectangles which covers the area 0,0,width,height
    that is not covered by any rectangle in rectlist, so the equivalent of
    filling all the rectangles in rectlist and then negating that.
    NOTE: if rectlist is empty then return an empty list, not a full frame.
    XXX need to take frame,overlay arguments and pass to DicomRect constructor.
    """
    # If not given anything to negate then return empty, not full frame rect.
    if not rectlist:
        return []
    # Create all new list elements from same type as existing
    RectType = type(rectlist[0])
    # Start with a rectangle which is full size
    r0 = deepcopy(rectlist[0]).set_rect(0, height-1, 0, width-1)
    newlist = [ r0 ]
    for inner_rect in rectlist:
        new2list = []
        for newrect in newlist:
            intersection = newrect.intersect_rect(inner_rect)
            if intersection.is_valid():
                # Replace newrect with four surrounding rect
                nl,nt,nr,nb = newrect.ltrb()
                l,t,r,b = intersection.ltrb()
                # Create a new object of same type as original, and preserve ocrengine value
                # Set coordinates in the order: (T,B,L,R)
                # XXX these are off-by-one and need fixed
                r1 = deepcopy(rectlist[0]).set_rect(min(t,nt), t, min(l,nl), max(r,nr))
                r2 = deepcopy(rectlist[0]).set_rect(t, b, min(l,nl), l)
                r3 = deepcopy(rectlist[0]).set_rect(t, b, r, max(r,nr))
                r4 = deepcopy(rectlist[0]).set_rect(b, max(b,nb), min(l,nl), max(r,nr))
                add_Rect_to_list(new2list, r1)
                add_Rect_to_list(new2list, r2)
                add_Rect_to_list(new2list, r3)
                add_Rect_to_list(new2list, r4)
            else:
                add_Rect_to_list(new2list, newrect)
        newlist = new2list
    # XXX should really coalesce all adjoining rectangles for efficiency
    return newlist


# ---------------------------------------------------------------------

def test_rect():
    r = Rect(1, 11, 2, 12) # T,B,L,R
    assert r.ltrb() == (2, 1, 12, 11)
    d = DicomRect(3, 33, 4, 44, 9, 10)
    assert d.F() == 9
    assert d.O() == 10
    d2 = DicomRect(4, 30, 5, 40)
    assert(r.contains(5,5) == True)
    assert(d.contains(5,5) == True)
    assert(d.contains(5,5) == True)
    assert(d.contains(5,5, 8, 8) == False)
    assert(d.contains(5,5, 9, 10) == True)
    # Check rectangle contained within a larger one
    assert(r.contains_rect(d) == False)
    assert(d.contains_rect(d2) == True)
    assert(d2.contains_rect(d) == False)
    # One rect contained in another is not added to list
    list1 = []
    list2 = []
    add_Rect_to_list(list1, r)
    add_Rect_to_list(list1, d)
    add_Rect_to_list(list1, d2)
    print(list1)
    add_Rect_to_list(list2, r)
    add_Rect_to_list(list2, d2)
    add_Rect_to_list(list2, d)
    print(list2)
    assert(len(list1) == 2)
    assert(len(list2) == 2)
    # Intersection should be same whichever way performed
    r1 = Rect(10,30,10,40) # T,B,L,R
    r2 = Rect(20,40,15,20)
    r_i = r1.intersect_rect(r2)
    assert(r_i.get_rect() == (20,30,15,20))
    r_i = r2.intersect_rect(r1)
    assert(r_i.get_rect() == (20,30,15,20))
    # Two separate rect do not intersect
    assert(r1.intersect_rect(Rect(100,100,101,101)).is_valid() == False)
    # An aligned rect does not intersect
    assert(r1.intersect_rect(Rect(30,40,10,40)).is_valid() == False)
    # Test a real US
    #42,452,943,732
    #238,37,786,448
    r3 = Rect(left=42,right=943,top=452,bottom=732)
    r4 = Rect(left=238,right=786,top=37,bottom=348)
    r5 = r3.intersect_rect(r4)
    assert(r5.is_valid() == False)
    list3 = []
    add_Rect_to_list(list3, r3)
    add_Rect_to_list(list3, r4)
    r_e_list = rect_exclusive_list(list3, 1024, 1024)
    expected = [
        Rect(left=0,top=0, right=1023,bottom=37),
        Rect(left=0,top=37, right=238,bottom=348),
        Rect(left=786,top=37, right=1023,bottom=348),
        Rect(left=0,top=348, right=1023,bottom=452),
        Rect(left=0,top=452, right=42,bottom=732),
        Rect(left=943,top=452, right=1023,bottom=732),
        Rect(left=0,top=732, right=1023,bottom=1023)
        ]
    assert(r_e_list == expected)
    # Plot for visual verification
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots()
    # Need a line to resize the plot area?
    ax.plot([0, 100],[0, 1000])
    # Plot the two rectangles
    l,t,w,h = r3.ltwh()
    ax.add_patch(Rectangle((l,t), w,h, facecolor='red', edgecolor='white'))
    l,t,w,h = r4.ltwh()
    ax.add_patch(Rectangle((l,t), w,h, facecolor='green', edgecolor='white'))
    # Plot outside the red/green rectangles in default blue
    for r in r_e_list:
        l,t,w,h = r.ltwh()
        ax.add_patch(Rectangle((l,t), w,h))
    # XXX if you want to visually see the result then uncomment plt.show()
    #plt.show()

