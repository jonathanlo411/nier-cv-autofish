## Log
Attempted HSV mask on otsu contouring on input1. Ideal values are `vmin 120` and `vmax 150`. Applying same values to input2 do not work. The static noise of input1 causes the minimums to be too high and actually highlights only the ripples with those values. So much so that you can see the black outline (instead of white outline) of the bob.
Learnings:
- Ripples will change color in different environments rendering baked in HSV mask values useless

`bg_subtraction` seems to work relatively well. Cons are that there is a warm up time but should not affect in this case. With this you can see the shape of the bob relatively well. Pixel count spikes look good with relatively minimal noise. Focus will be on identifying spikes from moving average (maybe 2s)

`template_matching` is far too chaotic on input 1 rendering it basically useless. May be able to work with some sort of mask but no good. With input2 it is better but only in the case where the bob is further away. if the ripples of the bob expand to outside of the ROI then the tracking is also way too chaotic. match score looks to chaotic.

`edge_detection` looks really good and can very visibly see the edges of the bob in both input1 and input2. Small issue is that the ripples will ocassionly brake the edge of the bob. This approach may work in conjunction with another model that evaluates if there is a square/rectangle and how long it is there/gone. One issue may be to soley rely on edge_pixels value. If the bob is close the edge pixels will actually drop instead of spike due to the bob taking up much space.

`optical_flow` is too noisy on both input1 and input2. Likely not useful for this use case. there are minor spikes but it is too unpredictable.

Learnings:
- Top canidates are `bg_subtraction` and `edge_detection`.