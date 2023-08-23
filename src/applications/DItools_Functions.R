## Pre-publishable version. Please report bugs/errors to gkaur001@dundee.ac.uk

## Library used for extracting DICOM tags
install.packages("oro.dicom")
library(oro.dicom)

## Invisible DICOM reading and plotting machinery powering functions DIplot(), DItag() & DIcheck()
plot.mech = function(itc = i) {
  x = readDICOMFile(itc, flipud = F, pixelData = F)
  rgb = as.integer(unique(x$hdr$value[x$hdr$name == "SamplesperPixel"]))
  mf = ifelse("NumberOfFrames" %in% x$hdr$name, as.integer(x$hdr$value[x$hdr$name == "NumberOfFrames"]), 1)
  signed = ifelse(unique(x$hdr$value[x$hdr$name == "PixelRepresentation"]) == 1, T, F)
  if (rgb == 3) {
    fsize = file.info(itc)$size
    fraw = readBin(itc, "raw", n = as.integer(fsize))
    rows = as.integer(x$hdr$value[x$hdr$name == "Rows"])[1]
    columns = as.integer(x$hdr$value[x$hdr$name == "Columns"])[1]
    bytes = as.integer(x$hdr$value[x$hdr$name == "BitsAllocated"])[1]/8
    length = max(as.integer(x$hdr$length[x$hdr$name == "PixelData"]))
    skip = fsize - length + 1
    framesize = rows*columns*rgb*bytes
    for (frame in 1:mf) {
      imageData = readBin(fraw[(skip+((frame-1)*framesize)):fsize], "integer", n = length/mf, size = bytes, signed = signed, endian = "little")
      imageData = array(imageData[c(seq(1, length/mf, rgb), seq(2, length/mf, rgb), seq(3, length/mf, rgb))], c(columns, rows, rgb))
      imageData = aperm(imageData, c(2, 1, 3))
      plot(as.raster(imageData/255))
      if (mf > 1) {print(paste("Frame#: ", frame, "/", mf))}
    } 
  } else {
    x = readDICOMFile(itc, flipud = F)
    if (mf == 1) {plot(as.raster(x$img/ifelse(signed, 255, max(x$img))))
    } else {
      for (frame in 1:mf) {
        y = x$img[,,frame]
        print(paste("Frame#: ", frame, "/", mf))
        plot(as.raster(y/ifelse(signed, 255, max(x$img))))
      }
    }
  }
}

## DIplot(): faster plotting for data exploration
DIplot = function(DICOMdir, # Root folder containing DICOMs or vector of relativefileURIs
                  recursive = F, # Plot DICOMs within sub-folders?
                  prompt = "next", # prompt for plotting next (on enter)
                  back = "<", # Reserved input for going back iteration(s) eg. < for 1, << for 2 and so on...
                  random = F) # Should the DICOMs be plotted in random order?
{
  if (any(file.exists(DICOMdir))) {
    f = DICOMdir[file.exists(DICOMdir) & endsWith(DICOMdir, ".dcm")]
  }
  if (dir.exists(DICOMdir)) {
    f = list.files(DICOMdir, full.names = T, recursive = recursive)
    f = f[endsWith(f, ".dcm")]
  }
  if (random) {f = sample(f)}
  l = ""
  for (i in f) {
    if (l != "" && unique(strsplit(l, "")[[1]]) == back) {
      fb = f[(which(f == i) - nchar(l) - 1):(which(f == i))]
      for (j in fb) {
        plot.mech(j)
        mtext(which(f == j), cex = 2)
        l = readline(prompt)
      }
    } else {
      plot.mech(i)
      mtext(which(f == i), cex = 2)
      l = readline(prompt)
    }
  }
}

## divvy(): To divide cohort into blocks for easy work division/allocation
## Example usage:
## DICOMdir = "//nimble//1718-0316//1718-0316//DX_SeriesInstanceUID_chest_10000_redacted//dicom//"
## saveDir = "//nimble//work//1718-0316//DX_SeriesInstanceUID_chest_10000_redacted_tags//"
## divvy(DICOMdir, saveDir)
## Output: n tagfiles will be created in the SaveDir folder

divvy = function(DICOMdir, saveDir, n = 10, recursive = T) {
  f = list.files(DICOMdir, full.names = T, recursive = recursive)
  f = f[endsWith(f, ".dcm")]
  f = split(f, 1:n)
  for (i in 1:n) {
    write.csv(data.frame(PK = f[[i]], Label = NA, Label_datetime = NA), paste(saveDir, "tagfile", i, ".csv", sep = ""), row.names = F)
  }
}


## DItag(): plotting and tagging DICOMs in specified folder location. Output is a tagfile in .csv format
## Usage: DItag(filename = "tagfile2", saveDir = "/nimble/work/1718-0316/test/")
DItag = function(filename = "tagfile", # Only name part of tagfile to be used, it will be suffixed by .csv by default
                 saveDir = "/nimble/work/1718-0316/test/", # Directory where output tagfile is saved
                 DefaultTag = "No PII", # The most frequently expected tag
                 prompt = "next",
                 progress = T, # "Are we there yet?"-prompt
                 interval = 50, # Progress prompt after how many DICOMs? To be used with progress = T else ignore
                 user = "Your Name", # username to be printed for signed datetime
                 back = "<") # Reserved input for going back iteration(s) eg. < for 1, << for 2 and so on.
{
  tagfile = read.csv(normalizePath(paste(saveDir, "/", filename, ".csv", sep = "")), stringsAsFactors = F)
  print(paste(length(tagfile$PK[is.na(tagfile$Label)]), "DICOMs remaining...", sep = " "))
  while(any(is.na(tagfile$Label))) {
    i = tagfile$PK[is.na(tagfile$Label)][1]
    plot.mech(i); mtext(which(tagfile$PK == i), cex = 2)
    l = readline(prompt)
    if (unique(strsplit(l, "")[[1]]) == back && l != "") {
      fb = tagfile$PK[(which(tagfile$PK == i) - nchar(l)):(which(tagfile$PK == i) - 1)]
      for (j in fb) {
        tagfile = read.csv(normalizePath(paste(saveDir, "/", filename, ".csv", sep = "")), stringsAsFactors = F)
        m = tagfile$Label[tagfile$PK == j]
        plot.mech(j); mtext(paste(m, " (", which(tagfile$PK == j), ")", sep = ""), cex = 2)
        b = readline("back")
        tagfile$Label[tagfile$PK == j] = ifelse(b == "", m, b)
        tagfile$Label_datetime[tagfile$PK == j] = paste("Tagged by", user, Sys.time(), sep = " ")
        write.csv(tagfile, normalizePath(paste(saveDir, "/", filename, ".csv", sep = "")), row.names = F)
      }
    } else {
      tagfile$Label[tagfile$PK == i] = ifelse(l == "", DefaultTag, l)
      tagfile$Label_datetime[tagfile$PK == i] = paste("Tagged by", user, Sys.time(), sep = " ")
      write.csv(tagfile, normalizePath(paste(saveDir, "/", filename, ".csv", sep = "")), row.names = F)
    }
    if (progress && sum(!is.na(tagfile$Label)) %% interval == 0) 
    {print(paste(sum(!is.na(tagfile$Label)), "/", nrow(tagfile), "... ", round(sum(!is.na(tagfile$Label))/(nrow(tagfile))*100), "%", sep = ""))}
  }
  t = table(tagfile$Label, dnn = "Exit Summary:")
  print(t)
  barplot(t, main = "Exit Summary")
  return(tagfile)
}
## DIcheck(): Function for plotting and validating output from DItag() 
DIcheck = function(tagfilePath, #path to tagfile from DItag() 
                   resume = F, # TRUE if returning from system crash or interval
                   back = "<", # Reserved input for going back iteration(s)
                   user = "Your Name", # username to be printed for signed datetime
                   tagCol = T, # coloured printing corresponding to tags for better cognition, recommended to be used if unique tags < 10, black if tagCol = F  
                   subset = F) # subset by label like "O" or c("O", "P")
  
{
  tagfile = read.csv(tagfilePath, stringsAsFactors = F)
  if (is.object(tagfile) && is.data.frame(tagfile) && c("PK", "Label") %in% names(tagfile)) {
    if (resume && "Check_datetime" %in% names(tagfile)) {print("Using existing tag file...")} else {
      tagfile$Check_datetime = rep(NA, nrow(tagfile)) }
    if (tagCol) {col = rainbow(length(unique(tagfile$Label)))[as.integer(factor(tagfile$Label))]}
    correction = ""
    for (i in ifelse(subset != F, tagfile$PK[is.na(tagfile$Check_datetime)], tagfile$PK[tagfile$Label %in% subset])) {
      if (correction != "" && unique(strsplit(correction, "")[[1]]) == back) {
        fb = tagfile$PK[(which(tagfile$PK == i) - nchar(correction) - 1):(which(tagfile$PK == i))]
        for (j in fb) {
          plot.mech(j)
          mtext(tagfile$Label[tagfile$PK == j], cex = 2)
          correction = readline("Enter for next or type in correction: ")
          tagfile$Label[tagfile$PK == j] = ifelse(correction == "" || unique(strsplit(correction, "")[[1]]) == back, 
                                                  tagfile$Label[tagfile$PK == j], correction)
          tagfile$Check_datetime[tagfile$PK == j] = paste("Checked by", user, Sys.time(), sep = " ")
        }
      } else {
        plot.mech(i)
        mtext(tagfile$Label[tagfile$PK == i], cex = 2, col = ifelse(tagCol, col[tagfile$PK == i], "black"))
        correction = readline("Enter for next or type in correction: ")
        tagfile$Label[tagfile$PK == i] = ifelse(correction == "" || unique(strsplit(correction, "")[[1]]) == back, 
                                                tagfile$Label[tagfile$PK == i], correction)
        tagfile$Check_datetime[tagfile$PK == i] = paste("Checked by", user, Sys.time(), sep = " ")
      }
      write.csv(tagfile, tagfilePath, row.names = F)
    }
    return(tagfile)} else {print("Invalid tagfile input")}
}

## Function to collate blocks of tagfiles 
## Output: A master tagfile will be created with the filename specified within the folder containing original tagfiles
DIbind = function(saveDir = "/nimble/work/1718-0316/CR_SeriesInstanceUID_chest_10000_redacted_tags/", # where blocks of tagfiles are kept
                  filename = "tagfile_master") # filename of the collated tagfile 
                  {
  f = list.files(saveDir, full.names = T)
  f = f[endsWith(f, ".csv")]
  t = data.frame(PK = character(), Label = character(), Label_datetime = character())
  for (i in f) {
    x = read.csv(i, stringsAsFactors = F)
    x = x[, which(colnames(x) %in% c("PK", "Label", "Label_datetime"))]
    t = rbind.data.frame(t, x)
  }
  write.csv(t, suppressWarnings(normalizePath(paste(saveDir, "/", filename, ".csv", sep = ""))), row.names = F)
  print(paste(filename, ".csv is saved in ", normalizePath(saveDir), sep = ""))
}
