""" Rectangle classes.
  Rect is the base class, holding only a rectangle (top, bottom, left, right).
  It also has 'contains' methods to test if a given rectangle is inside.
  DicomRect is a subclass which also holds frame, overlay properties.
  It also overrides the 'contains' method to check frame,overlay match.
  DicomOcrRect is a subclass which also holds output from OCR and NER
  tests for PII.
"""

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


# ---------------------------------------------------------------------

class DicomRect(Rect):
    """ Holds one rectangle and which image frame/overlay it applies to.
    Coordinates start at 0, top left.
    -1 means unset or not applicable for frame/overlay number.
    Overlay = -1 means frame is a standard frame.
    Overlay >= 0 means frame is within that overlay.
    """
    def __init__(self, top = None, bottom = None, left = None, right = None, frame = -1, overlay = -1):
        super().__init__(top, bottom, left, right)
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


# ---------------------------------------------------------------------

class DicomRectText(DicomRect):
    """ As a DicomRect but also holds details of any text found within,
    including the text, the source of the text, and whether it's PII.
    Right now ocrengine (enum), ocrtext (str), nerengine (enum), nerpii (enum)
    are all considered together so returned as a tuple from text_tuple().
    """
    def __init__(self, top = None, bottom = None, left = None, right = None, frame = -1, overlay = -1, ocrengine = -1, ocrtext='', nerengine = 0, nerpii = -1):
        super().__init__(top, bottom, left, right, frame, overlay)
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


# ---------------------------------------------------------------------

def add_Rect_to_list(rectlist, addrect):
    """ Extend the given list of rectangles with the given rectangle.
    Handles overlaps to ensure that the list does not contain any
    rectangles which would lie inside a larger rectangle.
    Works with Rect or DicomRect objects.
    """
    # If this one is larger we need to remove ALL smaller rects from the existing list
    rectlist[:] = [
        rect for rect in rectlist if
            not addrect.contains_rect(rect)
    ]
    # Now add the new one if it's not smaller than an existing one
    for rect in rectlist:
        # If a larger rectangle already exists then ignore this one
        if rect.contains_rect(addrect):
            return
    rectlist.append(addrect)


# ---------------------------------------------------------------------

def rect_exclusive_list(rectlist, width, height):
    """ Return a set of rectangles which covers the area 0,0,width,height
    that is not covered by any rectangle in rectlist, so the equivalent of
    filling all the rectangles in rectlist and then negating that.
    """
    # Start with a rectangle which is full size
    newlist = [ Rect(0, height-1, 0, width-1) ]
    for inner_rect in rectlist:
        new2list = []
        for newrect in newlist:
            intersection = newrect.intersect_rect(inner_rect)
            if intersection.is_valid():
                # Replace newrect with four surrounding rect
                nl,nt,nr,nb = newrect.ltrb()
                l,t,r,b = intersection.ltrb()
                # XXX need to check dimensions to ensure a valid rectangle before adding to list
                # XXX check we're not off-by-one with any of these coordinates
                new2list.append(Rect(min(t,nt), t, min(l,nl), max(r,nr))) # T,B,L,R
                new2list.append(Rect(t,b, min(l,nl), l))
                new2list.append(Rect(t,b, r, max(r,nr)))
                new2list.append(Rect(b, max(b,nb), min(l,nl), max(r,nr)))
            else:
                new2list.append(newrect)
        newlist = new2list
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
    plt.show()

